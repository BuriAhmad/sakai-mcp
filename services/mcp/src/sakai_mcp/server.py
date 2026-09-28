"""The fixed V1 MCP tool surface using the pinned MCP Python 2.2 SDK."""

from datetime import UTC, datetime
from math import isfinite
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl

from sakai_mcp.audit import audit_call, record_created
from sakai_mcp.config import Settings
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
    server = MCPServer(
        name="Sakai MCP",
        version="0.1.0",
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(str(settings.mcp_issuer)),
            resource_server_url=AnyHttpUrl(str(settings.mcp_public_url)),
            required_scopes=[settings.mcp_required_scope],
            validate_token_resource=False,  # The v2 GUID aud and HTTPS resource URI are verified separately.
        ),
    )

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

    return server
