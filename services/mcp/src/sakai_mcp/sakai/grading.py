"""Typed native grading operations; no MCP tool-name dispatch."""

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts.assignments import assignment_summaries, observation_revision
from sakai_mcp.contracts.existing_api import user_permissions
from sakai_mcp.contracts.grading_proposals import ProposalRecord
from sakai_mcp.contracts.grading_public import AssignmentListResult
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.existing_transport import ExistingApiTransport
from sakai_mcp.sakai.operations import ASSIGNMENTS, USER_PERMISSIONS
from sakai_mcp.sakai.transport import SakaiTransport
from sakai_mcp.workflows.access import AccessObservations
from sakai_mcp.workflows.captures import Captures
from sakai_mcp.workflows.grading_context import GradingContextReads
from sakai_mcp.workflows.grading_operations import GradingOperationsJournal
from sakai_mcp.workflows.grading_writes import GradingWrites
from sakai_mcp.workflows.selected_grades import selected_grades
from sakai_mcp.workflows.submissions import SubmissionReads


class GradingOperations:
    def __init__(
        self,
        transport: SakaiTransport,
        existing: ExistingApiTransport,
        submissions: SubmissionReads,
        captures: Captures,
    ) -> None:
        self.transport = transport
        self.settings = transport.settings
        self.existing = existing
        self.access = AccessObservations(existing)
        self.submissions = submissions
        self.captures = captures
        self.operations = GradingOperationsJournal(submissions, captures.records)
        self.writes = GradingWrites(submissions, self.operations)

    async def get_assignment_grading_context(
        self, principal: AccessToken, request: native.GetAssignmentGradingContextRequest
    ) -> native.GetAssignmentGradingContextResult:
        self._enabled()
        return await GradingContextReads(self.submissions).read(principal, request)

    async def list_assignment_submissions(
        self, principal: AccessToken, request: native.ListAssignmentSubmissionsRequest
    ) -> native.ListAssignmentSubmissionsResult:
        if not self.settings.assignment_grading_enabled:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        return await self.submissions.page(principal, request)

    async def get_assignment_submission(
        self, principal: AccessToken, request: native.GetAssignmentSubmissionRequest
    ) -> native.GetAssignmentSubmissionResult:
        if not self.settings.assignment_grading_enabled:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        return await self.submissions.detail(principal, request)

    async def export_assignment_submissions(
        self, principal: AccessToken, request: native.ExportAssignmentSubmissionsRequest
    ) -> native.ExportAssignmentSubmissionsResult:
        self._enabled()
        return await self.captures.export(principal, request)

    async def get_assignment_submission_export(
        self,
        principal: AccessToken,
        request: native.GetAssignmentSubmissionExportRequest,
    ) -> native.GetAssignmentSubmissionExportResult:
        self._enabled()
        return await self.captures.page(principal, request)

    def _enabled(self) -> None:
        if not self.settings.assignment_grading_enabled:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)

    async def save_assignment_grades(
        self, principal: AccessToken, request: native.SaveAssignmentGradesRequest
    ) -> native.SaveAssignmentGradesResult:
        self._enabled()
        return await self.writes.execute(principal, request, "save")

    async def release_assignment_grades(
        self, principal: AccessToken, request: native.ReleaseAssignmentGradesRequest
    ) -> native.ReleaseAssignmentGradesResult:
        self._enabled()
        return await self.writes.execute(principal, request, "release")

    async def get_assignment_grades(
        self, principal: AccessToken, request: native.GetAssignmentGradesRequest
    ) -> native.GetAssignmentGradesResult:
        self._enabled()
        return await selected_grades(self.submissions, principal, request)

    async def get_assignment_grading_operation(
        self,
        principal: AccessToken,
        request: native.GetAssignmentGradingOperationRequest,
    ) -> native.GetAssignmentGradingOperationResult:
        self._enabled()
        return await self.operations.read(principal, request)

    async def read_grading_file(
        self,
        principal: AccessToken,
        course: str,
        assignment: str,
        submission: str | None,
        file: str,
        revision: str,
    ) -> tuple[bytes, str, str]:
        if submission is not None:
            if not self.settings.assignment_grading_enabled:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            if file != "inline":
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            return await self.submissions.inline(
                principal, course, assignment, submission, revision
            )
        self._enabled()
        # Existing content ACL/availability/byte fidelity is not yet accepted.
        # Never fall back to a custom native file service.
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)

    async def read_grading_artifact(
        self,
        principal: AccessToken,
        course: str,
        assignment: str,
        export: str,
        artifact: str,
    ) -> tuple[bytes, str, str]:
        self._enabled()
        return await self.captures.artifact(
            principal, course, assignment, export, artifact
        )

    async def list_assignments(
        self, principal: AccessToken, course: str, cursor: str | None, limit: int
    ) -> AssignmentListResult:
        if not self.settings.assignment_grading_enabled:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if isinstance(limit, bool) or not 1 <= limit <= 100:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        actor = await self.access.actor(principal)
        access = await self.access.course(principal, actor, course)
        functions = access.functions
        if functions is None:
            permission = await self.existing.observe_json(
                USER_PERMISSIONS, principal, parameters={"site": course}
            )
            actor.require_same(permission)
            functions = user_permissions(permission.value)
        if "asn.grade" not in functions:
            # A4 hydrates whole-assignment evidence; never send it for a group TA.
            # Existing B3/B7 metadata-only native lists remain the narrower candidate.
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        observed = await self.existing.observe_json(
            ASSIGNMENTS, principal, parameters={"site": course}
        )
        actor.require_same(observed)
        items = assignment_summaries(observed.value, course)
        revision = observation_revision(
            {
                "actor": [actor.tenant, actor.object_id, actor.uid],
                "site": course,
                "items": items,
            }
        )
        offset = 0
        if cursor is not None:
            parts = cursor.split(":")
            if len(parts) != 2 or parts[0] != revision:
                raise SakaiError(ErrorCode.CONFLICT)
            if not parts[1].isascii() or not parts[1].isdecimal() or len(parts[1]) > 6:
                raise SakaiError(ErrorCode.VALIDATION_ERROR)
            offset = int(parts[1])
            if offset > len(items):
                raise SakaiError(ErrorCode.VALIDATION_ERROR)
        end = min(len(items), offset + limit)
        return AssignmentListResult.model_validate(
            {
                "items": items[offset:end],
                "snapshot_revision": revision,
                "next_cursor": f"{revision}:{end}" if end < len(items) else None,
            }
        )

    async def get_proposal(
        self,
        principal: AccessToken,
        course_id: str,
        assignment_id: str,
        proposal_id: str,
    ) -> ProposalRecord:
        self._enabled()
        return await self.captures.proposal(
            principal, course_id, assignment_id, proposal_id
        )
