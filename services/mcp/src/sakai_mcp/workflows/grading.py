"""Validate explicit grade payloads and read preserved legacy proposals.

Assessment belongs to the client workflow; no server evaluator is invoked.
"""

from typing import Literal

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts import grading_proposals as proposals
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.serialization import payload_hash
from sakai_mcp.sakai.client import SakaiClient


class GradingWorkflow:
    def __init__(self, client: SakaiClient) -> None:
        self.client = client

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
