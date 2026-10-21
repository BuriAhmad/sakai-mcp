"""Prepare immutable grading proposals from consistent, checksummed evidence."""

import asyncio
from typing import Any, Literal

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts import grading_proposals as proposals
from sakai_mcp.contracts.mcq_observation import mcq_observation
from sakai_mcp.contracts.setup_forms import core_supported
from sakai_mcp.contracts.submissions import entry
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.evaluator import evaluate_mcq
from sakai_mcp.grading.serialization import canonical, payload_hash
from sakai_mcp.sakai.client import SakaiClient
from sakai_mcp.workflows.assignment_setup import AssignmentSetup
from sakai_mcp.workflows.captures import assignment_revision
from sakai_mcp.workflows.resources import export_manifest


class GradingWorkflow:
    def __init__(self, client: SakaiClient) -> None:
        self.client = client
        self.prepare_slots = asyncio.Semaphore(2)

    async def prepare_mcq(
        self,
        token: AccessToken,
        course_id: str,
        assignment_id: str,
        export_id: str,
        proposal_id: str,
        config: proposals.MCQConfig,
    ) -> proposals.ProposalRecord:
        async with self.prepare_slots:
            return await self._prepare_mcq(
                token, course_id, assignment_id, export_id, proposal_id, config
            )

    async def _prepare_mcq(
        self,
        token: AccessToken,
        course_id: str,
        assignment_id: str,
        export_id: str,
        proposal_id: str,
        config: proposals.MCQConfig,
    ) -> proposals.ProposalRecord:
        client = self.client
        if (
            config.course_id != course_id
            or config.assignment_id != assignment_id
            or len(canonical(config.model_dump())) > 50_000
        ):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        # Reconcile a known receipt before doing any new work. Never replay a private write blindly.
        try:
            existing = await client.grading.get_proposal(
                token, course_id, assignment_id, proposal_id
            )
        except SakaiError as error:
            if error.code != ErrorCode.NOT_FOUND:
                raise
        else:
            if existing.export_id != export_id or existing.payload.config != config:
                raise SakaiError(ErrorCode.CONFLICT)
            return existing
        manifest = await export_manifest(
            client, token, course_id, assignment_id, export_id
        )
        if not manifest.completeness.complete or manifest.completeness.scope != "site":
            raise SakaiError(ErrorCode.CONFLICT)
        files: dict[str, bytes] = {}
        for artifact in manifest.artifacts:
            try:
                data, _, sha = await client.grading.read_grading_artifact(
                    token,
                    course_id,
                    assignment_id,
                    export_id,
                    artifact.artifact_id,
                )
                if sha != artifact.sha256 or len(data) != artifact.size_bytes:
                    raise SakaiError(ErrorCode.CONFLICT)
                files[artifact.artifact_id] = data
            except SakaiError as error:
                if error.code not in {
                    ErrorCode.DEPENDENCY_UNAVAILABLE,
                    ErrorCode.RATE_LIMITED,
                }:
                    raise
                continue
        roster: list[dict[str, Any]] = []
        seen: set[str] = set()
        cursor, revision = None, None
        while True:
            page = await client.grading.list_assignment_submissions(
                token,
                native.ListAssignmentSubmissionsRequest(
                    course_id=course_id,
                    assignment_id=assignment_id,
                    cursor=cursor,
                    limit=100,
                ),
            )
            if (
                not page.completeness.complete
                or page.completeness.scope != "site"
                or revision
                not in {
                    None,
                    page.snapshot_revision,
                }
            ):
                raise SakaiError(ErrorCode.CONFLICT)
            revision = page.snapshot_revision
            roster.extend(r.model_dump() for r in page.items)
            if len(roster) > 500:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            cursor = page.next_cursor
            if cursor is None:
                break
            if cursor in seen:
                raise SakaiError(ErrorCode.CONFLICT)
            seen.add(cursor)
        # Only after complete capture and roster gates: fresh existing HTTP
        # metadata, never the legacy full-context route or its native revision.
        _, assignment, current = await client.submissions.source(
            token, course_id, assignment_id
        )
        observed = {row.id: row for row in current}
        for row in roster:
            sid = row["submission_id"]
            if sid is None:
                continue
            current_row = observed.get(sid)
            if current_row is None:
                raise SakaiError(ErrorCode.CONFLICT)
            if (
                entry(current_row, assignment).content_revision
                != row["content_revision"]
            ):
                raise SakaiError(ErrorCode.CONFLICT)
        if set(observed) != {
            row["submission_id"] for row in roster if row["submission_id"] is not None
        }:
            raise SakaiError(ErrorCode.CONFLICT)
        form = await AssignmentSetup(client.submissions, None).edit_observation(
            token, course_id, assignment_id
        )
        core_supported(form)
        context = mcq_observation(assignment, assignment_revision(assignment), config)
        evidence = manifest.model_dump()
        evidence.update(course_id=course_id, assignment_id=assignment_id)
        # Path descriptors are legacy native DTO details, never required by this evaluator.
        for artifact in evidence["artifacts"]:
            artifact.pop("download_path")
            artifact.pop("relative_path")
        rows = evaluate_mcq(config.model_dump(), context, roster, evidence, files)
        payload = proposals.ProposalPayload(
            config=config, rows=[proposals.ProposalRow.model_validate(r) for r in rows]
        )
        record = await client.grading.create_proposal(
            token,
            course_id,
            assignment_id,
            proposal_id,
            payload,
            export_id,
        )
        return record

    async def prepare_grade_payload(
        self,
        token: AccessToken,
        course_id: str,
        assignment_id: str,
        kind: Literal["save", "release"],
        operation_id: str,
        expected_assignment_revision: str,
        grades: list[native.SaveRow | native.ReleaseRow],
    ) -> proposals.GradePayloadResult:
        client = self.client
        rows = [r.model_dump() for r in grades]
        value = {
            "course_id": course_id,
            "assignment_id": assignment_id,
            "operation_id": operation_id,
            "mode": "validate",
            "expected_assignment_revision": expected_assignment_revision,
            "payload_sha256": payload_hash(
                kind,
                course_id,
                assignment_id,
                expected_assignment_revision,
                rows,
            ),
            "grades": rows,
        }
        request_type = (
            native.SaveAssignmentGradesRequest
            if kind == "save"
            else native.ReleaseAssignmentGradesRequest
        )
        request = request_type.model_validate(value)
        if kind == "save":
            validation = await client.grading.save_assignment_grades(
                token, native.SaveAssignmentGradesRequest.model_validate(value)
            )
        else:
            validation = await client.grading.release_assignment_grades(
                token, native.ReleaseAssignmentGradesRequest.model_validate(value)
            )
        return proposals.GradePayloadResult(
            kind=kind,
            commit_arguments=request.model_copy(update={"mode": "commit"}),
            validation=validation,
        )

    async def get_proposal(
        self,
        token: AccessToken,
        course_id: str,
        assignment_id: str,
        proposal_id: str,
        cursor: str | None,
        limit: int,
    ) -> proposals.ProposalPage:
        client = self.client
        record = await client.grading.get_proposal(
            token, course_id, assignment_id, proposal_id
        )
        if isinstance(limit, bool) or not 1 <= limit <= 100:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        # The frozen public input schema permits numeric proposal offsets only.
        # The record itself is immutable and owner/source-authorized on every page.
        if cursor is not None and (
            not cursor.isascii() or not cursor.isdecimal() or len(cursor) > 6
        ):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        start = 0 if cursor is None else int(cursor)
        if start > len(record.payload.rows):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        end = min(len(record.payload.rows), start + limit)
        return proposals.ProposalPage(
            proposal_id=record.proposal_id,
            export_id=record.export_id,
            expires_at=record.expires_at,
            config=record.payload.config,
            rows=record.payload.rows[start:end],
            total=len(record.payload.rows),
            next_cursor=str(end) if end < len(record.payload.rows) else None,
        )
