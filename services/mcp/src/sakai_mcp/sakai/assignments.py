"""Existing HTTP assignment setup, publication and submitted metadata."""

from typing import Any

from mcp.server.auth.provider import AccessToken
from pydantic import ValidationError

from sakai_mcp.config import Settings
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
from sakai_mcp.workflows.assignment_setup import AssignmentSetup
from sakai_mcp.workflows.submissions import SubmissionReads


class AssignmentOperations:
    def __init__(
        self,
        settings: Settings,
        submissions: SubmissionReads,
        setup: AssignmentSetup,
    ) -> None:
        self.settings = settings
        self.submissions = submissions
        self.setup = setup

    async def get_course_submissions(
        self, principal: AccessToken, course_id: str, assignment_id: str
    ) -> list[dict[str, Any]]:
        return await self.submissions.metadata(principal, course_id, assignment_id)

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
        try:
            return await self.setup.context(
                principal, course_id, window_start, window_end
            )
        except ValidationError:
            raise SakaiError(ErrorCode.INTERNAL_ERROR) from None

    async def create_assignment(
        self, principal: AccessToken, request: CreateAssignmentRequest
    ) -> SetupResult:
        self._require_assignment_setup()
        try:
            validate_create(request)
        except ValueError:
            raise SakaiError(ErrorCode.VALIDATION_ERROR) from None
        return await self.setup.save(principal, request)

    async def publish_assignment(
        self, principal: AccessToken, request: PublishAssignmentRequest
    ) -> SetupResult:
        self._require_assignment_setup()
        return await self.setup.save(principal, request)
