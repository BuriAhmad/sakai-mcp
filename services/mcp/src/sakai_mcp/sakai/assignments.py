"""Assignment setup, publication, and legacy submission metadata."""

from typing import Any
from urllib.parse import urlencode

from mcp.server.auth.provider import AccessToken
from pydantic import ValidationError

from sakai_mcp.contracts.assignment_setup import (
    AssessmentContext,
    CreateAssignmentRequest,
    PublishAssignmentRequest,
    SetupResult,
)
from sakai_mcp.contracts.assignment_setup_validation import (
    validate_create,
    validate_window,
)
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.courses import list_result
from sakai_mcp.sakai.paths import segment
from sakai_mcp.sakai.transport import SakaiTransport


class AssignmentOperations:
    def __init__(self, transport: SakaiTransport) -> None:
        self.transport = transport
        self.settings = transport.settings

    async def get_course_submissions(
        self, principal: AccessToken, course_id: str, assignment_id: str
    ) -> list[dict[str, Any]]:
        path = f"/api/mcp/v1/courses/{segment(course_id)}/assignments/{segment(assignment_id)}/submissions"
        return list_result(
            await self.transport.request("GET", path, principal), "submissions"
        )

    def _require_assignment_setup(self) -> None:
        if not self.settings.assignment_setup_enabled:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)

    async def get_course_assessment_context(
        self,
        principal: AccessToken,
        course_id: str,
        window_start: str | None = None,
        window_end: str | None = None,
    ) -> AssessmentContext:
        self._require_assignment_setup()
        try:
            validate_window(window_start, window_end)
        except ValueError:
            raise SakaiError(ErrorCode.VALIDATION_ERROR) from None
        path = f"/api/mcp/v1/courses/{segment(course_id)}/assessment-context"
        if window_start is not None:
            path += "?" + urlencode(
                {"window_start": window_start, "window_end": window_end}
            )
        value = await self.transport.request("GET", path, principal)
        try:
            context = AssessmentContext.model_validate(value)
            if context.course.id != course_id:
                raise ValueError("Unexpected course")
            return context
        except (ValidationError, ValueError):
            raise SakaiError(ErrorCode.INTERNAL_ERROR) from None

    async def create_assignment(
        self, principal: AccessToken, request: CreateAssignmentRequest
    ) -> SetupResult:
        self._require_assignment_setup()
        try:
            validate_create(request)
        except ValueError:
            raise SakaiError(ErrorCode.VALIDATION_ERROR) from None
        path = f"/api/mcp/v1/courses/{segment(request.course_id)}/assignments"
        value = await self.transport.request(
            "POST",
            path,
            principal,
            request.model_dump(exclude={"course_id"}),
            unsupported=True,
        )
        return self._setup_result(value, request.course_id)

    async def publish_assignment(
        self, principal: AccessToken, request: PublishAssignmentRequest
    ) -> SetupResult:
        self._require_assignment_setup()
        path = f"/api/mcp/v1/courses/{segment(request.course_id)}/assignments/{segment(request.assignment_id)}/publish"
        value = await self.transport.request(
            "POST",
            path,
            principal,
            request.model_dump(exclude={"course_id", "assignment_id"}),
            unsupported=True,
        )
        return self._setup_result(value, request.course_id, request.assignment_id)

    @staticmethod
    def _setup_result(
        value: dict[str, Any], course_id: str, assignment_id: str | None = None
    ) -> SetupResult:
        try:
            result = SetupResult.model_validate(value)
            if result.course_id != course_id or (
                assignment_id is not None and result.assignment_id != assignment_id
            ):
                raise ValueError("Unexpected object")
            if (
                result.assignment is not None
                and result.assignment.id != result.assignment_id
            ):
                raise ValueError("Mismatched assignment")
            if result.outcome != "partial" and (
                result.assignment is None or result.failure or result.remaining_steps
            ):
                raise ValueError("Unverified completion")
            if result.outcome != "partial" and (
                result.verified_at is None
                or result.gradebook.status not in ("not_requested", "linked")
                or result.calendar.status not in ("not_requested", "linked")
            ):
                raise ValueError("Unverified links")
            if result.outcome == "partial" and (
                result.failure is None or not result.remaining_steps
            ):
                raise ValueError("Missing recovery information")
            return result
        except (ValidationError, ValueError):
            raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME) from None
