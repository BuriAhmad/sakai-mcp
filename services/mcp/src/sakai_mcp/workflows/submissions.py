"""Bounded site-wide submitted evidence. Incomplete observations block automation."""

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts.assignments import observation_revision
from sakai_mcp.contracts.existing_api import parse
from sakai_mcp.contracts.native_forms import native_url
from sakai_mcp.contracts.native_html import html, one
from sakai_mcp.contracts.submissions import (
    REASONS,
    AssignmentEvidence,
    WireSubmission,
    entry,
    submitted_rows,
)
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.serialization import digest
from sakai_mcp.sakai.browser_transport import BrowserTransport, NativePage
from sakai_mcp.sakai.existing_transport import ExistingApiTransport
from sakai_mcp.sakai.operations import ASSIGNMENT_ITEM
from sakai_mcp.workflows.access import AccessObservations, ActorIdentity
from sakai_mcp.workflows.placements import PlacementDiscovery


class SubmissionReads:
    def __init__(
        self, existing: ExistingApiTransport, browser: BrowserTransport
    ) -> None:
        self.existing = existing
        self.access = AccessObservations(existing)
        self.browser = browser
        self.discovery = PlacementDiscovery(existing)

    async def source(
        self, principal: AccessToken, site: str, assignment: str
    ) -> tuple[ActorIdentity, AssignmentEvidence, list[WireSubmission]]:
        actor, wire, rows, _ = await self.observed_source(principal, site, assignment)
        return actor, wire, rows

    async def observed_source(
        self,
        principal: AccessToken,
        site: str,
        assignment: str,
        *,
        all_pages: bool = False,
    ) -> tuple[
        ActorIdentity, AssignmentEvidence, list[WireSubmission], tuple[NativePage, ...]
    ]:
        actor = await self.access.actor(principal)
        access = await self.access.course(principal, actor, site)
        if "asn.grade" not in await self.access.functions(principal, access):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        # Native list gives positive current identity/individual-mode evidence
        # before requesting hydrated data. Never hydrate a known anonymous/group
        # assignment and claim that discarding identifiers repairs its privacy.
        grading_page = await self._individual_pages(
            principal, actor, site, assignment, all_pages=all_pages
        )
        observed = await self.existing.observe_json(
            ASSIGNMENT_ITEM, principal, parameters={"assignment": assignment}
        )
        actor.require_same(observed)
        wire = parse(AssignmentEvidence, observed.value)
        if wire.id != assignment or wire.context != site:
            raise SakaiError(ErrorCode.CONFLICT)
        return actor, wire, submitted_rows(wire), grading_page

    def _urls(self, page: NativePage, placement: str, action: str) -> list[str]:
        result: set[str] = set()
        for node in html(page.data).find():
            candidates = [node.attrs.get("href", "")]
            script = node.attrs.get("onclick", "")
            candidates.extend(
                re.findall(r"(?:window\.)?location\s*=\s*'([^']+)'", script)
            )
            candidates.extend(re.findall(r"VM_PP\.doPageNav\('([^']+)'", script))
            for candidate in candidates:
                if not candidate or candidate.startswith(("javascript:", "#")):
                    continue
                query = parse_qs(urlsplit(candidate).query, keep_blank_values=True)
                if action in query:
                    result.add(
                        native_url(self.browser.origin, page.url, candidate, placement)
                    )
        return sorted(result)

    async def _individual_pages(
        self,
        principal: AccessToken,
        actor: ActorIdentity,
        site: str,
        assignment: str,
        *,
        all_pages: bool = False,
    ) -> tuple[NativePage, ...]:
        bound = await self.discovery.resolve(principal, site, "sakai.assignment.grades")
        if bound.access.actor != actor:
            raise SakaiError(ErrorCode.UNAUTHENTICATED)
        placement = bound.target.placement
        async with self.browser.conversation(
            principal, placement, identity=actor.token_identity()
        ) as flow:
            page = await flow.navigate()
            seen: set[str] = set()
            for _ in range(20):
                signature = digest(page.data)
                if signature in seen:
                    raise SakaiError(ErrorCode.CONFLICT)
                seen.add(signature)
                target = []
                for url in self._urls(
                    page, placement, "eventSubmit_doGrade_assignment"
                ):
                    refs = parse_qs(urlsplit(url).query, keep_blank_values=True).get(
                        "assignmentId"
                    )
                    if refs == [f"/assignment/a/{site}/{assignment}"]:
                        target.append(url)
                if len(target) > 1:
                    raise SakaiError(ErrorCode.CONFLICT)
                if target:
                    grading = await flow.navigate(target[0])
                    pages = []
                    grading_seen: set[str] = set()
                    positive = False
                    for _ in range(20):
                        signature = digest(grading.data)
                        if signature in grading_seen:
                            raise SakaiError(ErrorCode.CONFLICT)
                        grading_seen.add(signature)
                        table = one(html(grading.data).find(id="submissionList"))
                        photos = table.find(tag="sakai-user-photo")
                        if any(
                            p.attrs.get("user-id") in {None, "", "blank"}
                            for p in photos
                        ):
                            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                        positive = positive or bool(photos)
                        pages.append(grading)
                        if not all_pages:
                            if not positive:
                                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                            return tuple(pages)
                        controls = [
                            n
                            for n in html(grading.data).find(tag="input")
                            if n.attrs.get("name") == "eventSubmit_doList_next"
                        ]
                        control = one(controls)
                        if "disabled" in control.attrs:
                            if not positive:
                                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                            return tuple(pages)
                        urls = self._urls(grading, placement, "eventSubmit_doList_next")
                        if len(urls) != 1:
                            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                        grading = await flow.navigate(urls[0])
                    raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                controls = [
                    n
                    for n in html(page.data).find(tag="input")
                    if n.attrs.get("name") == "eventSubmit_doList_next"
                ]
                if len(controls) != 1 or "disabled" in controls[0].attrs:
                    raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                next_urls = self._urls(page, placement, "eventSubmit_doList_next")
                if len(next_urls) != 1:
                    raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                page = await flow.navigate(next_urls[0])
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)

    async def metadata(
        self, principal: AccessToken, site: str, assignment: str
    ) -> list[dict[str, Any]]:
        _, _, rows = await self.source(principal, site, assignment)
        rows.sort(
            key=lambda r: (
                r.dateSubmittedEpochSeconds is None,
                r.dateSubmittedEpochSeconds or 0,
                r.id.encode("utf-16-be"),
            )
        )
        return [
            {
                "id": r.id,
                "submitterIds": [u.id for u in r.submitters],
                "submittedAt": r.dateSubmittedEpochSeconds,
            }
            for r in rows[:100]
        ]

    async def page(
        self, principal: AccessToken, request: native.ListAssignmentSubmissionsRequest
    ) -> native.ListAssignmentSubmissionsResult:
        actor, assignment, rows = await self.source(
            principal, request.course_id, request.assignment_id
        )
        items = [
            entry(r, assignment)
            for r in sorted(rows, key=lambda r: r.id.encode("utf-16-be"))
        ]
        revision = observation_revision(
            {
                "actor": [actor.tenant, actor.object_id, actor.uid],
                "site": request.course_id,
                "assignment": request.assignment_id,
                "rows": [r.model_dump() for r in items],
            }
        )
        offset = 0
        if request.cursor is not None:
            parts = request.cursor.split(":")
            if len(parts) != 2 or parts[0] != revision:
                raise SakaiError(ErrorCode.CONFLICT)
            if not parts[1].isascii() or not parts[1].isdecimal() or len(parts[1]) > 6:
                raise SakaiError(ErrorCode.VALIDATION_ERROR)
            offset = int(parts[1])
            if offset > len(items):
                raise SakaiError(ErrorCode.VALIDATION_ERROR)
        end = min(offset + request.limit, len(items))
        return native.ListAssignmentSubmissionsResult(
            items=items[offset:end],
            next_cursor=f"{revision}:{end}" if end < len(items) else None,
            snapshot_revision=revision,
            observed_at=datetime.now(UTC).isoformat(),
            completeness=native.Completeness(
                complete=False, scope="site", reasons=REASONS
            ),
            warnings=[
                "submitted_individual_rows_only",
                "unsubmitted_and_orphan_rows_not_enumerated",
            ],
        )

    async def detail(
        self, principal: AccessToken, request: native.GetAssignmentSubmissionRequest
    ) -> native.GetAssignmentSubmissionResult:
        _, assignment, rows = await self.source(
            principal, request.course_id, request.assignment_id
        )
        matches = [r for r in rows if r.id == request.submission_id]
        if len(matches) != 1:
            # A dropped serializer row is not proof of a missing native record.
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        row = matches[0]
        return native.GetAssignmentSubmissionResult(
            submission=entry(row, assignment),
            inline_text=row.submittedText,
            inline_content_type="text/html" if row.submittedText is not None else None,
            feedback_comment=row.feedbackComment,
            feedback_sha256=digest(row.feedbackComment.encode())
            if row.feedbackComment is not None
            else None,
            observed_at=datetime.now(UTC).isoformat(),
            warnings=REASONS,
        )

    async def inline(
        self,
        principal: AccessToken,
        site: str,
        assignment: str,
        submission: str,
        revision: str,
    ) -> tuple[bytes, str, str]:
        result = await self.detail(
            principal,
            native.GetAssignmentSubmissionRequest(
                course_id=site, assignment_id=assignment, submission_id=submission
            ),
        )
        if result.submission.content_revision != revision:
            raise SakaiError(ErrorCode.CONFLICT)
        if result.inline_text is None:
            raise SakaiError(ErrorCode.NOT_FOUND)
        data = result.inline_text.encode("utf-8")
        if len(data) > 65535:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        return data, "text/html", digest(data)
