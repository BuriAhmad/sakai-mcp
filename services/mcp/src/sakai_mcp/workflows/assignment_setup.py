"""Existing Assignment forms: bounded planning, single-send saves and publication."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts import assignment_setup as public
from sakai_mcp.contracts.assessment_metadata import assessment_metadata
from sakai_mcp.contracts.native_html import html, one
from sakai_mcp.contracts.setup_forms import (
    DATES,
    PARTS,
    SUBMISSION_TYPES,
    ListedAssignment,
    SetupForm,
    checked,
    core_supported,
    listed_assignments,
    local_instant,
    portal_zone,
    reference,
    setup_form,
)
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.serialization import canonical, digest
from sakai_mcp.sakai.browser_transport import NativeConversation, NativePage
from sakai_mcp.sakai.operations import CURRENT_SITE, ITEM_DATA
from sakai_mcp.storage.base import RecordOwner
from sakai_mcp.storage.records import PrivateRecords
from sakai_mcp.workflows.access import ActorIdentity
from sakai_mcp.workflows.operation_journal import OperationJournal
from sakai_mcp.workflows.placements import BoundPlacement
from sakai_mcp.workflows.submissions import SubmissionReads

WARNINGS = [
    "native_reads_not_atomic_or_cas",
    "readback_is_an_observation_not_a_causal_receipt",
    "native_initial_persistence_is_not_private_first",
    "strict_assignment_release_and_deleted_fields_not_observed",
    "new_invocation_is_a_new_intent_not_a_safe_retry",
]


def restrict_request(
    request: public.CreateAssignmentRequest | public.PublishAssignmentRequest,
) -> None:
    if request.calendar_deadline != "none":
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if request.gradebook.mode == "new_external" and (
        not request.gradebook.release_to_students
        or not request.gradebook.count_toward_course_grade
    ):
        # Native addExternalAssessment exposes/counts the new item by default.
        # Never create that transient state when the requested policy forbids it.
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if (
        request.gradebook.mode == "new_external"
        and request.gradebook.category_id is not None
    ):
        category = request.gradebook.category_id
        if (
            not category.isascii()
            or not category.isdecimal()
            or not 0 < int(category) < 2**63
            or str(int(category)) != category
        ):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if isinstance(request, public.CreateAssignmentRequest):
        try:
            title_units = len(request.title.encode("utf-16-le")) // 2
            instruction_bytes = len(request.instructions.encode("utf-8"))
        except UnicodeError:
            raise SakaiError(ErrorCode.VALIDATION_ERROR) from None
        if (
            title_units > 100
            or instruction_bytes > 65535
            or request.attachment_resource_refs
        ):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if request.resubmission.count not in {-1, *range(11)}:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if (
            request.submission_type == "non_electronic"
            and request.resubmission.count != 0
        ):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        for value in (
            request.open_at,
            request.due_at,
            request.close_at,
            request.visible_at,
            request.resubmission.until,
        ):
            if value is not None:
                instant = datetime.fromisoformat(value)
                if instant.second or instant.microsecond or instant.year > 2099:
                    raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if len(format(Decimal(str(request.max_points)), "f")) > 11:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)


class AssignmentSetup:
    def __init__(
        self, submissions: SubmissionReads, records: PrivateRecords | None
    ) -> None:
        self.source = submissions
        self.journal = OperationJournal(records) if records is not None else None

    async def _metadata(
        self, token: AccessToken, actor: ActorIdentity, site: str
    ) -> tuple[list[public.GradebookItem], list[public.Category], list[str]]:
        observed = await self.source.existing.observe_json(
            ITEM_DATA, token, parameters={"site": site}
        )
        actor.require_same(observed)
        return assessment_metadata(observed.value, site)

    async def _listing(
        self, flow: NativeConversation, page: NativePage, site: str, placement: str
    ) -> dict[str, ListedAssignment]:
        result: dict[str, ListedAssignment] = {}
        seen = set()
        for _ in range(20):
            signature = digest(page.data)
            if signature in seen:
                raise SakaiError(ErrorCode.CONFLICT)
            seen.add(signature)
            if html(page.data).find(css="sak-banner-error"):
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            rows = listed_assignments(page, self.source.browser.origin, placement, site)
            if result.keys() & rows.keys() or len(result) + len(rows) > 500:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            result.update(rows)
            control = one(
                [
                    n
                    for n in html(page.data).find(tag="input")
                    if n.attrs.get("name") == "eventSubmit_doList_next"
                ]
            )
            if "disabled" in control.attrs:
                return result
            urls = self.source._urls(page, placement, "eventSubmit_doList_next")
            if len(urls) != 1:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            page = await flow.navigate(urls[0])
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)

    async def _open(
        self, token: AccessToken, site: str, *, create: bool
    ) -> tuple[BoundPlacement, frozenset[str]]:
        bound = await self.source.discovery.resolve(
            token, site, "sakai.assignment.grades"
        )
        functions = await self.source.access.functions(token, bound.access)
        needed = {"asn.new", "asn.revise"} if create else {"asn.revise"}
        # Group-only edit authority must not be mistaken for site-wide authority.
        if not needed <= set(functions):
            raise SakaiError(ErrorCode.FORBIDDEN)
        return bound, functions

    async def edit_observation(
        self,
        token: AccessToken,
        site: str,
        assignment: str,
        *,
        expected_actor: ActorIdentity | None = None,
    ) -> SetupForm:
        bound, functions = await self._open(token, site, create=False)
        if "gradebook.editAssignments" not in functions:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        actor, placement = bound.access.actor, bound.target.placement
        if expected_actor is not None and actor != expected_actor:
            raise SakaiError(ErrorCode.UNAUTHENTICATED)
        async with self.source.browser.conversation(
            token, placement, identity=actor.token_identity()
        ) as flow:
            rows = await self._listing(flow, await flow.navigate(), site, placement)
            target = rows.get(assignment)
            if target is None or target.draft:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            return setup_form(
                await flow.navigate(target.edit_url),
                self.source.browser.origin,
                placement,
                actor,
                site,
            )

    async def context(
        self, token: AccessToken, site: str, start: str | None, end: str | None
    ) -> public.AssessmentContext:
        bound, functions = await self._open(token, site, create=True)
        if "gradebook.editAssignments" not in functions:
            raise SakaiError(ErrorCode.FORBIDDEN)
        actor, placement = bound.access.actor, bound.target.placement
        async with self.source.browser.conversation(
            token, placement, identity=actor.token_identity()
        ) as flow:
            first = await flow.navigate()
            zone = portal_zone(first, actor, site)
            add = self.source._urls(first, placement, "eventSubmit_doNew_assignment")
            rows = await self._listing(flow, first, site, placement)
            if len(add) != 1:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            revisions: dict[str, str | None] = {}
            for row in list(rows.values())[:20]:
                try:
                    existing = setup_form(
                        await flow.navigate(row.edit_url),
                        self.source.browser.origin,
                        placement,
                        actor,
                        site,
                    )
                    if reference(existing.value("assignmentId"), site) != row.id:
                        raise SakaiError(ErrorCode.CONFLICT)
                    revisions[row.id] = existing.revision
                except SakaiError as error:
                    if error.code != ErrorCode.UNSUPPORTED_CAPABILITY:
                        raise
                    revisions[row.id] = None
            new = setup_form(
                await flow.navigate(add[0]),
                self.source.browser.origin,
                placement,
                actor,
                site,
            )
            # The source template conditionally emits a multi-Gradebook component.
            # Require the create-item choice as positive evidence of this section.
            if not new.node.find(id="create-gradebook-item"):
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            groups = bool(new.node.find(tag="sakai-multi-gradebook"))
        observed = await self.source.existing.observe_json(
            CURRENT_SITE, token, parameters={"site": site}
        )
        actor.require_same(observed)
        title = (
            observed.value.get("title") if isinstance(observed.value, dict) else None
        )
        if not isinstance(title, str) or not title or len(title) > 255:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        warnings = [
            "assignment_list_permission_and_filter_scoped",
            "calendar_not_read",
            "strict_assignment_configuration_fields_unavailable",
            "native_reads_may_initialize_tool_preferences",
            "timezone_is_effective_acting_user_zone_not_verified_course_policy",
        ]
        # Preserve the strict public Assignment schema; do not fill unknown release,
        # deleted or integration flags with false. These are explicitly partial
        # metadata observations for planning, not full Assignment objects.
        for select in new.node.find(tag="select"):
            if select.attrs.get("name") == "new_assignment_category":
                choices = select.find(tag="option")
                if len(choices) > 500:
                    raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                for option in choices:
                    value = option.attrs.get("value", "")
                    if value != "-1" and "disabled" not in option.attrs:
                        warnings.append(
                            "gradebook_category_choice_metadata_only: "
                            + json.dumps(
                                {"id": value, "name": option.text()}, ensure_ascii=False
                            )
                        )
        for row in rows.values():
            warnings.append(
                "assignment_metadata_only: "
                + json.dumps(
                    {
                        "id": row.id,
                        "title": row.title,
                        "draft": row.draft,
                        "configuration_revision": revisions.get(row.id),
                    },
                    ensure_ascii=False,
                )
            )
        book = public.AssessmentContextGradebook(
            available=False,
            reason="independent_gradebook_metadata_unavailable",
            group_gradebooks_enabled=groups,
            category_mode=None,
            grade_entry_type=None,
            display_released_items=None,
            course_grade_displayed=None,
            categories=[],
            items=[],
        )
        if not groups:
            items, categories, metadata_warnings = await self._metadata(
                token, actor, site
            )
            warnings.extend(metadata_warnings)
            book = public.AssessmentContextGradebook(
                available=True,
                reason="partial_existing_item_category_metadata_settings_and_due_dates_unavailable",
                group_gradebooks_enabled=False,
                category_mode=None,
                grade_entry_type=None,
                display_released_items=None,
                course_grade_displayed=None,
                categories=categories,
                items=items,
            )
        now = datetime.now(UTC)
        window_first = (now - timedelta(days=14)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return public.AssessmentContext(
            course=public.AssessmentContextCourse(
                id=site, title=title, timezone=zone.key, timezone_source="unknown"
            ),
            observed_at=now.isoformat(),
            capabilities=public.AssessmentContextCapabilities(
                create_site_assignment="asn.new" in functions,
                revise_assignment="asn.revise" in functions,
                edit_gradebook_items="gradebook.editAssignments" in functions,
                read_calendar="calendar.read" in functions,
                add_calendar_event="calendar.new" in functions,
                create_announcement="annc.new" in functions,
            ),
            complete=False,
            sections=public.AssessmentContextSections(
                assignments=public.AssessmentContextSectionsAssignments(
                    status="unavailable",
                    reason="strict_full_assignment_fields_unavailable_metadata_only_in_warnings",
                ),
                gradebook=public.AssessmentContextSectionsGradebook(
                    status="permission_scoped" if book.available else "unavailable",
                    reason=book.reason,
                ),
                calendar=public.AssessmentContextSectionsCalendar(
                    status="unavailable", reason="native_calendar_read_not_adopted"
                ),
            ),
            assignments=[],
            gradebook=book,
            calendar=public.AssessmentContextCalendar(
                scope="site_main",
                window_start=start or window_first.isoformat(),
                window_end=end or (window_first + timedelta(days=56)).isoformat(),
                events=[],
            ),
            warnings=warnings,
        )

    def _changes(
        self,
        snapshot: SetupForm,
        request: public.CreateAssignmentRequest | public.PublishAssignmentRequest,
    ) -> dict[str, str | list[str]]:
        changes: dict[str, str | list[str]] = {
            "option": "save"
            if isinstance(request, public.CreateAssignmentRequest)
            and request.publication == "draft"
            else "post",
            "eventSubmit_doAssignment_form": "",
        }
        form = snapshot.form
        if snapshot.locale.lower().replace("_", "-").split("-", 1)[0] != "en":
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if isinstance(request, public.CreateAssignmentRequest):
            # Source-defined supported fields only. Unknown controls stay native.
            changes.update(
                {
                    "new_assignment_title": request.title,
                    "new_assignment_instructions": request.instructions,
                    "new_assignment_grade_type": "3",
                    "new_assignment_grade_points": format(
                        Decimal(str(request.max_points)), "f"
                    ),
                    "new_assignment_submission_type": SUBMISSION_TYPES[
                        request.submission_type
                    ],
                    "assignTo": "individuals",
                }
            )
            snapshot.option("new_assignment_grade_type", "3")
            snapshot.option(
                "new_assignment_submission_type",
                SUBMISSION_TYPES[request.submission_type],
            )
            for key in ("selectedGroups", "allowResToggle", "allowVisibleDateToggle"):
                if key in form.names:
                    changes[key] = []
            for key in ("new_assignment_grade_assignment",):
                if key in form.names:
                    changes[key] = "true"
            stamps = {
                DATES[0]: request.open_at,
                DATES[1]: request.due_at,
                DATES[2]: request.close_at,
            }
            if request.visible_at is not None:
                if (
                    DATES[3] not in snapshot.dates
                    or "allowVisibleDateToggle" not in form.names
                ):
                    raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                changes["allowVisibleDateToggle"] = "on"
                stamps[DATES[3]] = request.visible_at
            if request.resubmission.count != 0:
                if (
                    DATES[4] not in snapshot.dates
                    or "allowResToggle" not in form.names
                    or request.resubmission.until is None
                ):
                    raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                snapshot.option(
                    "allow_resubmit_number", str(request.resubmission.count)
                )
                changes.update(
                    {
                        "allowResToggle": "on",
                        "allow_resubmit_number": str(request.resubmission.count),
                    }
                )
                stamps[DATES[4]] = request.resubmission.until
            for prefix, value in stamps.items():
                stamp = datetime.fromisoformat(value).astimezone(snapshot.zone)
                if stamp.year > 2099:
                    raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                # Recheck wall-time round trip; native atZone otherwise chooses a fold.
                local_instant(stamp.replace(tzinfo=None).isoformat(), snapshot.zone)
                for part, number in zip(
                    PARTS,
                    (stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute),
                    strict=True,
                ):
                    changes[prefix + part] = str(number)
        else:
            core_supported(snapshot)
        # Do not let add-form defaults silently activate anonymous, peer, review,
        # due-calendar or auto-announcement policies.
        for node in snapshot.node.find(tag="input"):
            if "checked" in node.attrs and node.attrs.get("name") in {
                "new_assignment_use_peer_assessment",
                "new_assignment_use_review_service",
                "new_assignment_check_anonymous_grading",
                "new_assignment_check_auto_announce",
                "new_assignment_check_add_due_date",
            }:
                if (
                    isinstance(request, public.CreateAssignmentRequest)
                    and node.attrs.get("name")
                    in {
                        "new_assignment_check_auto_announce",
                        "new_assignment_check_add_due_date",
                    }
                    and "disabled" not in node.attrs
                ):
                    changes[node.attrs["name"]] = []
                else:
                    raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            if node.attrs.get("name") == "attachments":
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        for rubric in snapshot.node.find(tag="sakai-rubric-association"):
            if rubric.attrs.get("association", "") not in {"", "null", "{}"}:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if snapshot.node.find(tag="sakai-multi-gradebook"):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if request.gradebook.mode == "new_external":
            choice = one(snapshot.node.find(id="create-gradebook-item"))
            if "disabled" in choice.attrs or choice.attrs.get("value") != "add":
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            changes.update(
                {
                    "new_assignment_send_to_gradebook": "true",
                    "new_assignment_add_to_gradebook": "add",
                }
            )
            if (
                request.gradebook.category_id is None
                and "new_assignment_category" in form.names
            ):
                # GbGradebookData marks uncategorized items uncounted whenever
                # categories are enabled. This request explicitly requires counting.
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            if (
                request.gradebook.category_id is not None
                or "new_assignment_category" in form.names
            ):
                selected_category = request.gradebook.category_id or "-1"
                snapshot.option("new_assignment_category", selected_category)
                changes["new_assignment_category"] = selected_category
        else:
            if isinstance(request, public.PublishAssignmentRequest) and checked(
                form, "new_assignment_send_to_gradebook"
            ):
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            if "new_assignment_send_to_gradebook" in form.names:
                changes["new_assignment_send_to_gradebook"] = []
        form.values(changes)
        return changes

    async def save(
        self,
        token: AccessToken,
        request: public.CreateAssignmentRequest | public.PublishAssignmentRequest,
    ) -> public.SetupResult:
        restrict_request(request)
        if self.journal is None:
            raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE)
        create = isinstance(request, public.CreateAssignmentRequest)
        bound, functions = await self._open(token, request.course_id, create=create)
        actor, placement = bound.access.actor, bound.target.placement
        if request.gradebook.mode == "new_external":
            if "gradebook.editAssignments" not in functions:
                raise SakaiError(ErrorCode.FORBIDDEN)
            preflight_items, _, _ = await self._metadata(
                token, actor, request.course_id
            )
            if isinstance(request, public.CreateAssignmentRequest) and any(
                item.title == request.title for item in preflight_items
            ):
                raise SakaiError(ErrorCode.CONFLICT)
        async with self.source.browser.conversation(
            token, placement, identity=actor.token_identity()
        ) as flow:
            first = await flow.navigate()
            before = await self._listing(flow, first, request.course_id, placement)
            if isinstance(request, public.CreateAssignmentRequest):
                if any(r.title == request.title for r in before.values()):
                    raise SakaiError(ErrorCode.CONFLICT)
                add = self.source._urls(
                    first, placement, "eventSubmit_doNew_assignment"
                )
                if len(add) != 1:
                    raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                edit = await flow.navigate(add[0])
            else:
                current = before.get(request.assignment_id)
                if current is None:
                    raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                edit = await flow.navigate(current.edit_url)
            snapshot = setup_form(
                edit, self.source.browser.origin, placement, actor, request.course_id
            )
            if isinstance(request, public.CreateAssignmentRequest):
                if snapshot.value("assignmentId"):
                    raise SakaiError(ErrorCode.CONFLICT)
            else:
                if (
                    reference(snapshot.value("assignmentId"), request.course_id)
                    != request.assignment_id
                    or snapshot.revision != request.expected_assignment_revision
                ):
                    raise SakaiError(ErrorCode.CONFLICT)
                # Reposting an already published assignment can regenerate integrations.
                if current is None or not current.draft:
                    raise SakaiError(ErrorCode.CONFLICT)
            changes = self._changes(snapshot, request)
            intended = snapshot.form.values(changes)
            # Fresh actor/site authority immediately before durable send intent.
            again, _ = await self._open(token, request.course_id, create=create)
            if again.access.actor != actor or again.target != bound.target:
                raise SakaiError(ErrorCode.UNAUTHENTICATED)
            owner = RecordOwner(
                actor.tenant, actor.object_id, actor.uid, request.course_id, "__setup__"
            )
            operation = str(uuid4())
            intent: dict[str, Any] = {
                "kind": "assignment-create" if create else "assignment-publish",
                "request": request.model_dump(),
                "baseline_ids": sorted(before),
                "observed_revision": snapshot.revision,
            }
            hashed = digest(canonical(intent))
            await self.journal.prepare(
                owner, operation, intent, hashed, now=datetime.now(UTC)
            )
            await self.journal.begin_send(
                owner, operation, hashed, now=datetime.now(UTC)
            )
            try:
                posted = await flow.submit(snapshot.form, changes, academic=True)
                after = await self._listing(flow, posted, request.course_id, placement)
                if isinstance(request, public.CreateAssignmentRequest):
                    candidates = set(after) - set(before)
                    if len(candidates) != 1:
                        raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME)
                    identifier = candidates.pop()
                else:
                    identifier = request.assignment_id
                row = after.get(identifier)
                expected_draft = (
                    isinstance(request, public.CreateAssignmentRequest)
                    and request.publication == "draft"
                )
                if row is None or row.draft != expected_draft:
                    raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME)
                readback = setup_form(
                    await flow.navigate(row.edit_url),
                    self.source.browser.origin,
                    placement,
                    actor,
                    request.course_id,
                )
                if (
                    reference(readback.value("assignmentId"), request.course_id)
                    != identifier
                ):
                    raise SakaiError(ErrorCode.CONFLICT)
                observed_values = readback.form.values({})
                keys = {
                    k
                    for k, _ in intended
                    if k.startswith(
                        (
                            "new_assignment_open_",
                            "new_assignment_due_",
                            "new_assignment_close_",
                            "new_assignment_visible_",
                            "allow_resubmit_",
                        )
                    )
                } | {
                    "new_assignment_title",
                    "new_assignment_instructions",
                    "new_assignment_grade_type",
                    "new_assignment_grade_points",
                    "new_assignment_submission_type",
                    "assignTo",
                    "allowVisibleDateToggle",
                    "allowResToggle",
                    "new_assignment_send_to_gradebook",
                }
                if not any(k == "allowVisibleDateToggle" for k, _ in intended):
                    keys = {k for k in keys if not k.startswith(DATES[3])}
                if not any(k == "allowResToggle" for k, _ in intended):
                    keys = {k for k in keys if not k.startswith("allow_resubmit_")}
                instructions_changed = False
                for key in keys:
                    target = [v for k, v in intended if k == key]
                    actual = [v for k, v in observed_values if k == key]
                    if (
                        key == "new_assignment_grade_points"
                        and len(target) == len(actual) == 1
                        and Decimal(target[0]) == Decimal(actual[0])
                    ):
                        continue
                    if actual != target:
                        if key == "new_assignment_instructions":
                            instructions_changed = True
                        else:
                            raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME)
                if readback.zone != snapshot.zone:
                    raise SakaiError(ErrorCode.CONFLICT)
                await self.journal.observe(
                    owner,
                    operation,
                    {
                        "assignment_id": identifier,
                        "configuration_revision": readback.revision,
                        "draft": row.draft,
                        "stage": "assignment_form_observed",
                    },
                    partial=True,
                    now=datetime.now(UTC),
                )
                book = public.GradebookLink(
                    gradebook_item_id=None,
                    external_id=None,
                    category_id=None,
                    mode="none",
                    status="not_requested",
                    released=None,
                    counted=None,
                )
                if request.gradebook.mode == "new_external":
                    expected_ref = f"/assignment/a/{request.course_id}/{identifier}"
                    try:
                        items, _, _ = await self._metadata(
                            token, actor, request.course_id
                        )
                        matches = [
                            item
                            for item in items
                            if item.external_id == expected_ref
                            and item.external_app == "sakai.assignment.grades"
                        ]
                        if len(matches) > 1:
                            raise SakaiError(ErrorCode.CONFLICT)
                        link = matches[0] if matches else None
                        if link is not None and (
                            not link.externally_maintained
                            or link.gradable_reference not in {None, expected_ref}
                        ):
                            raise SakaiError(ErrorCode.CONFLICT)
                    except SakaiError as error:
                        if error.code not in {
                            ErrorCode.UNSUPPORTED_CAPABILITY,
                            ErrorCode.DEPENDENCY_UNAVAILABLE,
                            ErrorCode.INTERNAL_ERROR,
                            ErrorCode.NOT_FOUND,
                            ErrorCode.RATE_LIMITED,
                        }:
                            raise
                        link = None
                    if link is None:
                        book = public.GradebookLink(
                            gradebook_item_id=None,
                            external_id=None,
                            category_id=None,
                            mode="new_external",
                            status="unknown",
                            released=None,
                            counted=None,
                        )
                    else:
                        book = public.GradebookLink(
                            gradebook_item_id=link.id,
                            external_id=link.external_id,
                            category_id=link.category_id,
                            mode="new_external",
                            status="linked"
                            if link.released is True
                            and link.counted is True
                            and link.category_id == request.gradebook.category_id
                            else "mismatch",
                            released=link.released,
                            counted=link.counted,
                        )
                await self.journal.observe(
                    owner,
                    operation,
                    {
                        "assignment_id": identifier,
                        "configuration_revision": readback.revision,
                        "draft": row.draft,
                        "gradebook": book.model_dump(),
                    },
                    partial=True,
                    now=datetime.now(UTC),
                )
                return public.SetupResult(
                    outcome="partial",
                    course_id=request.course_id,
                    assignment_id=identifier,
                    assignment=None,
                    gradebook=book,
                    calendar=public.CalendarLink(
                        event_id=None, calendar_reference=None, status="not_requested"
                    ),
                    verified_at=datetime.now(UTC).isoformat(),
                    remaining_steps=["verify_assignment", "verify_setup"]
                    if instructions_changed
                    else ["verify_setup"],
                    warnings=[
                        *WARNINGS,
                        "configuration_revision: " + readback.revision,
                        "observed_draft: " + str(row.draft).lower(),
                        "operation_id: " + operation,
                        "gradebook_observation_status: " + book.status,
                        *(
                            ["native_instruction_readback_differs_verify_saved_content"]
                            if instructions_changed
                            else []
                        ),
                    ],
                    failure=public.SetupResultFailure(
                        code="PARTIAL_SUCCESS",
                        stage="verify_setup",
                        reason=(
                            "Assignment saved and publication observed; native instructions differ from the request and need review. Inspect the saved ID; do not repeat create."
                            if instructions_changed
                            else "Assignment form fields and publication observed; strict release/deleted/full integration fields remain unverified. Inspect the saved ID; do not repeat create."
                        ),
                        retry_safe=False,
                    ),
                )
            except Exception as error:
                try:
                    await self.journal.unknown(owner, operation, now=datetime.now(UTC))
                except SakaiError:
                    pass
                if isinstance(error, SakaiError) and error.code in {
                    ErrorCode.UNAUTHENTICATED,
                    ErrorCode.FORBIDDEN,
                }:
                    raise
                raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME) from None
