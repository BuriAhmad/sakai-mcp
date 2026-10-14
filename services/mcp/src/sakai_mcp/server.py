"""The fixed V1 MCP tool surface using the pinned MCP Python 2.2 SDK."""

from datetime import UTC, datetime
from math import isfinite
from typing import Any, Literal, get_type_hints

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl, ValidationError

from sakai_mcp.assessment_models import (
    AssessmentContext,
    CreateAssignmentRequest,
    GradebookConfiguration,
    PublishAssignmentRequest,
    Resubmission,
    SetupResult,
)
from sakai_mcp.audit import audit_call, record_created, record_outcome
from sakai_mcp.config import Settings
from sakai_mcp.resource_server import SakaiResourceServer
from sakai_mcp.sakai_client import ErrorCode, SakaiClient, SakaiError

READ_HINTS = ToolAnnotations(
    read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
WRITE_HINTS = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False
)


def _principal() -> AccessToken:
    token = get_access_token()
    if token is None:
        raise ToolError(ErrorCode.UNAUTHENTICATED.value)
    return token


def _page(rows: list[dict[str, Any]], cursor: str | None, limit: int | None, settings: Settings, cap: int) -> dict[str, Any]:
    size = settings.page_size_default if limit is None else limit
    if not isinstance(size, int) or isinstance(size, bool) or not 1 <= size <= settings.page_size_max:
        raise ToolError(ErrorCode.VALIDATION_ERROR.value)
    if cursor is None:
        offset = 0
    elif isinstance(cursor, str) and cursor.isascii() and cursor.isdecimal() and len(cursor) <= 6:
        offset = int(cursor)
    else:
        raise ToolError(ErrorCode.VALIDATION_ERROR.value)
    end = min(offset + size, len(rows))
    return {
        "items": rows[offset:end],
        "next_cursor": str(end) if end < len(rows) else None,
        "source_limit_reached": len(rows) >= cap,
    }


def _announcement(row: dict[str, Any]) -> dict[str, Any]:
    posted = row.get("postedAt")
    if not isinstance(posted, int) or isinstance(posted, bool):
        raise ToolError(ErrorCode.INTERNAL_ERROR.value)
    try:
        posted_at = datetime.fromtimestamp(posted / 1000, UTC).isoformat().replace("+00:00", "Z")
    except (OverflowError, ValueError):
        raise ToolError(ErrorCode.INTERNAL_ERROR.value) from None
    return {
        "id": row.get("id"),
        "title": row.get("title"),
        "body": row.get("body"),
        "posted_at": posted_at,
    }


def _submission(row: dict[str, Any]) -> dict[str, Any]:
    stamp = row.get("submittedAt")
    if stamp is not None:
        try:
            if isinstance(stamp, (int, float)) and not isinstance(stamp, bool) and isfinite(stamp) and stamp >= 0:
                # Sakai 25.2 serializes AssignmentSubmission Instant as epoch seconds.
                parsed = datetime.fromtimestamp(stamp, UTC)
            elif isinstance(stamp, str):
                parsed = datetime.fromisoformat(stamp)
                if parsed.tzinfo is None:
                    raise ValueError("timestamp has no timezone")
            else:
                raise ValueError("unsupported timestamp")
            stamp = parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
        except (OverflowError, ValueError):
            raise ToolError(ErrorCode.INTERNAL_ERROR.value) from None
    return {"id": row.get("id"), "submitter_ids": row.get("submitterIds"), "submitted_at": stamp}


def create_server(settings: Settings, client: SakaiClient, verifier: TokenVerifier) -> MCPServer:
    server = SakaiResourceServer(
        name="Sakai MCP",
        version="0.2.0",
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(str(settings.mcp_issuer)),
            resource_server_url=AnyHttpUrl(settings.mcp_resource_uri),
            required_scopes=[settings.mcp_required_scope],
            validate_token_resource=False,  # The v2 GUID aud and HTTPS resource URI are verified separately.
        ),
    )

    server.grading_client = client
    server.grading_enabled = settings.assignment_grading_enabled

    @server.tool(description="List courses the signed-in Sakai user can visit.", annotations=READ_HINTS)
    async def list_my_courses() -> dict[str, Any]:
        async with audit_call("list_my_courses", "read"):
            try:
                courses = await client.list_my_courses(_principal())
                return {"courses": courses}
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    @server.tool(description="Read only the signed-in user's released grades in a course.", annotations=READ_HINTS)
    async def get_my_grades(course_id: str) -> dict[str, Any]:
        async with audit_call("get_my_grades", "read", course_id):
            try:
                grades = await client.get_my_grades(_principal(), course_id)
                return {"grades": grades}
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    @server.tool(description="Read visible announcements from a course.", annotations=READ_HINTS)
    async def get_course_announcements(
        course_id: str, cursor: str | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        async with audit_call("get_course_announcements", "read", course_id):
            try:
                announcements = await client.get_course_announcements(_principal(), course_id)
                return _page([_announcement(row) for row in announcements], cursor, limit, settings, 50)
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    @server.tool(description="Read submission metadata the signed-in grader may see.", annotations=READ_HINTS)
    async def get_course_submissions(
        course_id: str, assignment_id: str, cursor: str | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        async with audit_call("get_course_submissions", "read", course_id, assignment_id):
            try:
                submissions = await client.get_course_submissions(_principal(), course_id, assignment_id)
                return _page([_submission(row) for row in submissions], cursor, limit, settings, 100)
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    @server.tool(description="Create one plain course announcement when Sakai permits it.", annotations=WRITE_HINTS)
    async def create_course_announcement(course_id: str, title: str, body: str) -> dict[str, Any]:
        async with audit_call("create_course_announcement", "write", course_id):
            try:
                announcement = await client.create_course_announcement(_principal(), course_id, title, body)
                record_created(announcement["id"])
                return {"announcement": announcement}
            except SakaiError as error:
                raise ToolError(error.code.value) from None

    if settings.assignment_setup_enabled:
        @server.tool(description="Inspect instructor assessment metadata, links and completeness before setup.", annotations=READ_HINTS)
        async def get_course_assessment_context(
            course_id: str, window_start: str | None = None, window_end: str | None = None
        ) -> AssessmentContext:
            async with audit_call("get_course_assessment_context", "read", course_id):
                try:
                    return await client.get_course_assessment_context(_principal(), course_id, window_start, window_end)
                except SakaiError as error:
                    raise ToolError(error.code.value) from None

        async def create_assignment(
            course_id: str, title: str, instructions: str, timezone: str, visible_at: str | None,
            open_at: str, due_at: str, close_at: str, max_points: float,
            submission_type: Literal["text_only", "attachments_only", "text_and_attachments", "non_electronic", "single_attachment"],
            resubmission: Resubmission, publication: Literal["draft", "published"],
            attachment_resource_refs: list[str], gradebook: GradebookConfiguration,
            calendar_deadline: Literal["none", "course_calendar"],
        ) -> SetupResult:
            async with audit_call("create_assignment", "write", course_id):
                try:
                    request = CreateAssignmentRequest(
                        course_id=course_id, title=title, instructions=instructions, timezone=timezone,
                        visible_at=visible_at, open_at=open_at, due_at=due_at, close_at=close_at,
                        max_points=max_points, submission_type=submission_type, resubmission=resubmission,
                        publication=publication, attachment_resource_refs=attachment_resource_refs,
                        gradebook=gradebook, calendar_deadline=calendar_deadline,
                    )
                    result = await client.create_assignment(_principal(), request)
                    record_created(result.assignment_id)
                    if result.outcome == "partial":
                        record_outcome("PARTIAL_SUCCESS")
                    return result
                except ValidationError:
                    raise ToolError(ErrorCode.VALIDATION_ERROR.value) from None
                except SakaiError as error:
                    raise ToolError(error.code.value) from None

        async def publish_assignment(
            course_id: str, assignment_id: str, expected_assignment_revision: str,
            gradebook: GradebookConfiguration, calendar_deadline: Literal["none", "course_calendar"],
        ) -> SetupResult:
            async with audit_call("publish_assignment", "write", course_id, assignment_id):
                try:
                    request = PublishAssignmentRequest(
                        course_id=course_id, assignment_id=assignment_id,
                        expected_assignment_revision=expected_assignment_revision,
                        gradebook=gradebook, calendar_deadline=calendar_deadline,
                    )
                    result = await client.publish_assignment(_principal(), request)
                    if result.outcome == "partial":
                        record_outcome("PARTIAL_SUCCESS")
                    return result
                except ValidationError:
                    raise ToolError(ErrorCode.VALIDATION_ERROR.value) from None
                except SakaiError as error:
                    raise ToolError(error.code.value) from None

        # Publish the same field bounds as the validated contracts, including nested definitions.
        create_assignment.__annotations__.update(get_type_hints(CreateAssignmentRequest, include_extras=True))
        publish_assignment.__annotations__.update(get_type_hints(PublishAssignmentRequest, include_extras=True))
        server.add_tool(create_assignment, description="Create a points-based site assignment and coordinate approved linked objects. Never replay an ambiguous create.", annotations=WRITE_HINTS)
        server.add_tool(publish_assignment, description="Promote or resume one known assignment using its observed revision. Creates only missing owned links.", annotations=WRITE_HINTS)

    if settings.assignment_grading_enabled:
        from sakai_mcp.grading_tools import register_grading_tools
        register_grading_tools(server, client)

    return server
