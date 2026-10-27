"""Bounded existing HTTP grading: single individual integer score, unlinked item."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from urllib.parse import urlencode

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts.assignments import observation_revision
from sakai_mcp.contracts.grading_preservation import plain, preserved, score
from sakai_mcp.contracts.native_html import one
from sakai_mcp.contracts.setup_forms import SetupForm, checked, core_supported
from sakai_mcp.contracts.submissions import AssignmentEvidence, WireSubmission, entry
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.serialization import canonical, digest, payload_hash
from sakai_mcp.workflows.access import ActorIdentity
from sakai_mcp.workflows.assignment_setup import AssignmentSetup
from sakai_mcp.workflows.captures import assignment_revision
from sakai_mcp.workflows.grading_operations import GradingOperationsJournal, Request
from sakai_mcp.workflows.selected_grades import paged_releases
from sakai_mcp.workflows.submissions import SubmissionReads

WARNINGS = [
    "advisory_observations_not_native_cas",
    "single_individual_integer_score_no_gradebook_subset",
    "non_atomic_readback_does_not_prove_causation",
    "strict_full_assignment_state_unavailable",
]


@dataclass(frozen=True, repr=False)
class Observation:
    actor: ActorIdentity = field(repr=False)
    assignment: AssignmentEvidence = field(repr=False)
    row: WireSubmission = field(repr=False)
    released: bool
    form: SetupForm = field(repr=False)

    def fingerprint(self) -> str:
        return observation_revision(
            {
                "actor": [
                    self.actor.tenant,
                    self.actor.object_id,
                    self.actor.uid,
                    self.actor.eid,
                ],
                "row": self.row.model_dump(),
                "assignment": assignment_revision(self.assignment),
                "released": self.released,
                "form": self.form.revision,
            }
        )


class GradingWrites:
    def __init__(self, source: SubmissionReads, journal: GradingOperationsJournal):
        self.source, self.journal = source, journal
        self.setup = AssignmentSetup(source, None)

    async def observe(self, token: AccessToken, request: Request) -> Observation:
        actor, assignment, rows, pages = await self.source.observed_source(
            token, request.course_id, request.assignment_id, all_pages=True
        )
        selected = request.grades[0]
        matches = [r for r in rows if r.id == selected.submission_id]
        if len(matches) != 1 or matches[0].submitters[0].id != selected.sakai_user_id:
            raise SakaiError(ErrorCode.FORBIDDEN)
        releases = paged_releases(
            pages, self.source.browser.origin, request.course_id, request.assignment_id
        )
        flag = releases.get((selected.submission_id, selected.sakai_user_id))
        if flag is None:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        form = await self.setup.edit_observation(
            token, request.course_id, request.assignment_id, expected_actor=actor
        )
        core_supported(form)
        control = one(
            [
                n
                for n in form.node.find(tag="input")
                if n.attrs.get("name") == "new_assignment_send_to_gradebook"
            ]
        )
        if (
            "disabled" in control.attrs
            or checked(form.form, "new_assignment_send_to_gradebook")
            or form.node.find(tag="sakai-multi-gradebook")
            or form.locale.lower().replace("_", "-").split("-", 1)[0] != "en"
        ):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        # No raw scale assumption; the first subset accepts integral displayed scores.
        if assignment.gradeScale != "SCORE_GRADE_TYPE":
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        return Observation(actor, assignment, matches[0], flag, form)

    def preflight(
        self, request: Request, observed: Observation, kind: str
    ) -> dict[str, str]:
        selected = request.grades[0]
        current = entry(observed.row, observed.assignment)
        composite = observation_revision(
            {"grade": current.grade_revision, "released": observed.released}
        )
        if (
            request.expected_assignment_revision
            != assignment_revision(observed.assignment)
            or selected.expected_content_revision != current.content_revision
            or selected.expected_grade_revision
            not in {current.grade_revision, composite}
            or not observed.row.userSubmission
            or observed.released
            or observed.row.returned
        ):
            raise SakaiError(ErrorCode.CONFLICT)
        values = preserved(observed.row)
        if isinstance(selected, native.SaveRow) and kind == "save":
            value = selected.score
            if selected.feedback.action != "preserve":
                values["feedbackComment"] = (
                    plain(selected.feedback.text)
                    if selected.feedback.action == "replace"
                    else ""
                )
        elif isinstance(selected, native.ReleaseRow) and kind == "release":
            value = selected.expected_score
            if (
                not observed.row.graded
                or current.score is None
                or Decimal(current.score) != Decimal(value)
                or selected.expected_feedback_sha256
                != (
                    digest(observed.row.feedbackComment.encode())
                    if observed.row.feedbackComment is not None
                    else None
                )
            ):
                raise SakaiError(ErrorCode.CONFLICT)
        else:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        score(
            value,
            observed.assignment.gradeScaleMaxPoints
            or observed.assignment.maxGradePoint,
        )
        if Decimal(value) > Decimal(observed.form.value("new_assignment_grade_points")):
            raise SakaiError(ErrorCode.CONFLICT)
        values.update(
            courseId=request.course_id,
            siteId=request.course_id,
            gradableId=request.assignment_id,
            submissionId=selected.submission_id,
            studentId=selected.sakai_user_id,
            grade=value,
            gradeOption="save" if kind == "save" else "return",
        )
        return values

    def receipt(
        self,
        request: Request,
        kind: Literal["save", "release"],
        observed: Observation,
        *,
        validated: bool,
    ) -> native.OperationReceipt:
        item = entry(observed.row, observed.assignment)
        return native.OperationReceipt(
            operation_id=request.operation_id,
            kind=kind,
            mode=request.mode,
            payload_sha256=request.payload_sha256,
            outcome="validated" if validated else "partial",
            observed_at=datetime.now(UTC).isoformat(),
            warnings=WARNINGS,
            rows=[
                native.RowReceipt(
                    submission_id=observed.row.id,
                    sakai_user_id=observed.row.submitters[0].id,
                    stage="validated"
                    if validated
                    else "saved"
                    if kind == "save"
                    else "assignment_released",
                    content_revision=item.content_revision,
                    grade_revision=observation_revision(
                        {"grade": item.grade_revision, "released": observed.released}
                    ),
                    assignment_score=item.score,
                    grade_released=observed.released,
                    returned=observed.row.returned,
                    gradebook_score=None,
                    reason="advisory_only" if validated else "observed_not_atomic",
                    retry_action="none",
                )
            ],
        )

    async def execute(
        self, token: AccessToken, request: Request, kind: Literal["save", "release"]
    ) -> native.OperationReceipt:
        if len(canonical(request.model_dump())) > 60_000:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        if len(request.grades) != 1:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if (
            payload_hash(
                kind,
                request.course_id,
                request.assignment_id,
                request.expected_assignment_revision,
                [r.model_dump() for r in request.grades],
            )
            != request.payload_sha256
        ):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        if request.mode == "commit":
            self.journal.store()
            previous = await self.journal.existing(token, request)
            if previous is not None:
                return previous
        observed = await self.observe(token, request)
        values = self.preflight(request, observed, kind)
        if len(urlencode(values).encode()) > 60_000:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if request.mode == "validate":
            return self.receipt(request, kind, observed, validated=True)

        async def send() -> native.OperationReceipt:
            before = await self.observe(token, request)
            self.preflight(request, before, kind)
            if before.fingerprint() != observed.fingerprint():
                raise SakaiError(ErrorCode.CONFLICT)
            response = await self.source.existing.grade_form(token, values)
            try:
                before.actor.require_same(response)
                if response.value["submission"]["id"] != observed.row.id:
                    raise ValueError
                after = await self.observe(token, request)
                if (
                    after.actor != before.actor
                    or assignment_revision(after.assignment)
                    != assignment_revision(observed.assignment)
                    or after.form.revision != observed.form.revision
                    or Decimal(after.row.grade or "-1") != Decimal(values["grade"])
                    or not after.row.graded
                    or after.released != (kind == "release")
                    or after.row.returned != (kind == "release")
                    or preserved(after.row)
                    != {
                        k: v
                        for k, v in values.items()
                        if k
                        in {
                            "privateNotes",
                            "feedbackText",
                            "feedbackComment",
                            "resubmitNumber",
                            "resubmitDate",
                            "extensionDate",
                        }
                    }
                    or {
                        k: v
                        for k, v in (after.row.properties or {}).items()
                        if k != "last_graded_date"
                    }
                    != {
                        k: v
                        for k, v in (observed.row.properties or {}).items()
                        if k != "last_graded_date"
                    }
                    or entry(after.row, after.assignment).content_revision
                    != entry(observed.row, observed.assignment).content_revision
                ):
                    raise ValueError
                return self.receipt(request, kind, after, validated=False)
            except (KeyError, TypeError, ValueError, SakaiError):
                raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME) from None

        return await self.journal.commit(token, request, kind, send)
