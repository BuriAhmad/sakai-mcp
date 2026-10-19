"""Typed native grading operations; no MCP tool-name dispatch."""

import json
from typing import Any, TypeVar
from urllib.parse import urlencode

from mcp.server.auth.provider import AccessToken
from pydantic import ValidationError

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts.grading_proposals import ProposalPayload, ProposalRecord
from sakai_mcp.contracts.grading_public import AssignmentListResult
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.paths import segment
from sakai_mcp.sakai.transport import SakaiTransport

Result = TypeVar("Result", bound=native.GradingModel)


class GradingOperations:
    def __init__(self, transport: SakaiTransport) -> None:
        self.transport = transport
        self.settings = transport.settings

    async def get_assignment_grading_context(
        self, principal: AccessToken, request: native.GetAssignmentGradingContextRequest
    ) -> native.GetAssignmentGradingContextResult:
        return await self._send(
            principal,
            request,
            "GET",
            "/grading-context",
            native.GetAssignmentGradingContextResult,
            mutation=False,
            query_post=False,
        )

    async def list_assignment_submissions(
        self, principal: AccessToken, request: native.ListAssignmentSubmissionsRequest
    ) -> native.ListAssignmentSubmissionsResult:
        return await self._send(
            principal,
            request,
            "GET",
            "/grading-submissions",
            native.ListAssignmentSubmissionsResult,
            mutation=False,
            query_post=False,
        )

    async def get_assignment_submission(
        self, principal: AccessToken, request: native.GetAssignmentSubmissionRequest
    ) -> native.GetAssignmentSubmissionResult:
        return await self._send(
            principal,
            request,
            "GET",
            f"/grading-submissions/{segment(request.submission_id)}",
            native.GetAssignmentSubmissionResult,
            mutation=False,
            query_post=False,
        )

    async def export_assignment_submissions(
        self, principal: AccessToken, request: native.ExportAssignmentSubmissionsRequest
    ) -> native.ExportAssignmentSubmissionsResult:
        return await self._send(
            principal,
            request,
            "POST",
            "/grading-exports",
            native.ExportAssignmentSubmissionsResult,
            mutation=True,
            query_post=False,
        )

    async def get_assignment_submission_export(
        self,
        principal: AccessToken,
        request: native.GetAssignmentSubmissionExportRequest,
    ) -> native.GetAssignmentSubmissionExportResult:
        return await self._send(
            principal,
            request,
            "GET",
            f"/grading-exports/{segment(request.export_id)}",
            native.GetAssignmentSubmissionExportResult,
            mutation=False,
            query_post=False,
        )

    async def save_assignment_grades(
        self, principal: AccessToken, request: native.SaveAssignmentGradesRequest
    ) -> native.SaveAssignmentGradesResult:
        return await self._send(
            principal,
            request,
            "POST",
            "/grading-save",
            native.SaveAssignmentGradesResult,
            mutation=True,
            query_post=False,
        )

    async def release_assignment_grades(
        self, principal: AccessToken, request: native.ReleaseAssignmentGradesRequest
    ) -> native.ReleaseAssignmentGradesResult:
        return await self._send(
            principal,
            request,
            "POST",
            "/grading-release",
            native.ReleaseAssignmentGradesResult,
            mutation=True,
            query_post=False,
        )

    async def get_assignment_grades(
        self, principal: AccessToken, request: native.GetAssignmentGradesRequest
    ) -> native.GetAssignmentGradesResult:
        return await self._send(
            principal,
            request,
            "POST",
            "/grading-grades/query",
            native.GetAssignmentGradesResult,
            mutation=False,
            query_post=True,
        )

    async def get_assignment_grading_operation(
        self,
        principal: AccessToken,
        request: native.GetAssignmentGradingOperationRequest,
    ) -> native.GetAssignmentGradingOperationResult:
        return await self._send(
            principal,
            request,
            "GET",
            f"/grading-operations/{segment(request.operation_id)}",
            native.GetAssignmentGradingOperationResult,
            mutation=False,
            query_post=False,
        )

    async def _send(
        self,
        principal: AccessToken,
        request: native.GradingModel,
        method: str,
        suffix: str,
        result_type: type[Result],
        *,
        mutation: bool,
        query_post: bool = False,
    ) -> Result:
        payload = request.model_dump()
        course, assignment = payload.pop("course_id"), payload.pop("assignment_id")
        root = self.grading_root(course, assignment)
        if (
            method == "POST"
            and len(json.dumps(payload, ensure_ascii=False).encode()) > 60_000
        ):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        if method == "GET":
            query = {
                k: v
                for k, v in payload.items()
                if k in {"cursor", "limit"} and v is not None
            }
            if query:
                suffix += "?" + urlencode(query)
        try:
            value = await self.transport.request(
                method,
                root + suffix,
                principal,
                payload if method == "POST" else None,
                unsupported=True,
            )
        except SakaiError as error:
            if query_post and error.code == ErrorCode.AMBIGUOUS_WRITE_OUTCOME:
                raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE) from None
            raise
        try:
            return result_type.model_validate(value)
        except ValidationError:
            raise SakaiError(
                ErrorCode.AMBIGUOUS_WRITE_OUTCOME
                if mutation
                else ErrorCode.INTERNAL_ERROR
            ) from None

    def grading_root(self, course: str, assignment: str) -> str:
        if not self.settings.assignment_grading_enabled:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        return (
            f"/api/mcp/v1/courses/{segment(course)}/assignments/{segment(assignment)}"
        )

    async def read_grading_file(
        self,
        principal: AccessToken,
        course: str,
        assignment: str,
        submission: str | None,
        file: str,
        revision: str,
    ) -> tuple[bytes, str, str]:
        root = self.grading_root(course, assignment)
        suffix = (
            f"/grading-submissions/{segment(submission)}/files/{segment(file)}"
            if submission
            else f"/grading-files/{segment(file)}"
        )
        return await self.transport.read_bytes(
            principal, root + suffix + "?" + urlencode({"revision": revision})
        )

    async def read_grading_artifact(
        self,
        principal: AccessToken,
        course: str,
        assignment: str,
        export: str,
        artifact: str,
    ) -> tuple[bytes, str, str]:
        path = (
            self.grading_root(course, assignment)
            + f"/grading-exports/{segment(export)}/artifacts/{segment(artifact)}"
        )
        return await self.transport.read_bytes(principal, path)

    async def list_assignments(
        self, principal: AccessToken, course: str, cursor: str | None, limit: int
    ) -> AssignmentListResult:
        if not self.settings.assignment_grading_enabled:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        path = (
            f"/api/mcp/v1/courses/{segment(course)}/grading-assignments?"
            + urlencode(
                {
                    k: v
                    for k, v in {"cursor": cursor, "limit": limit}.items()
                    if v is not None
                }
            )
        )
        value = await self.transport.request("GET", path, principal, unsupported=True)
        try:
            return AssignmentListResult.model_validate(value)
        except ValidationError:
            raise SakaiError(ErrorCode.INTERNAL_ERROR) from None

    async def get_proposal(
        self,
        principal: AccessToken,
        course_id: str,
        assignment_id: str,
        proposal_id: str,
    ) -> ProposalRecord:
        path = (
            self.grading_root(course_id, assignment_id)
            + "/grading-proposals/"
            + segment(proposal_id)
        )
        value = await self.transport.request("GET", path, principal, unsupported=True)
        return self._proposal_record(value, proposal_id, None, mutation=False)

    async def create_proposal(
        self,
        principal: AccessToken,
        course_id: str,
        assignment_id: str,
        proposal_id: str,
        payload: ProposalPayload,
        export_id: str,
    ) -> ProposalRecord:
        path = self.grading_root(course_id, assignment_id) + "/grading-proposals"
        body = {
            "proposal_id": proposal_id,
            "export_id": export_id,
            "payload": payload.model_dump(),
        }
        if len(json.dumps(body, ensure_ascii=False).encode()) > 900_000:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        value = await self.transport.request(
            "POST", path, principal, body, unsupported=True
        )
        return self._proposal_record(value, proposal_id, export_id, mutation=True)

    @staticmethod
    def _proposal_record(
        value: dict[str, Any],
        proposal_id: str,
        export_id: str | None,
        *,
        mutation: bool,
    ) -> ProposalRecord:
        try:
            result = ProposalRecord.model_validate(value)
            if result.proposal_id != proposal_id or (
                export_id is not None and result.export_id != export_id
            ):
                raise ValueError("Wrong receipt")
            return result
        except (ValidationError, ValueError):
            raise SakaiError(
                ErrorCode.AMBIGUOUS_WRITE_OUTCOME
                if mutation
                else ErrorCode.INTERNAL_ERROR
            ) from None
