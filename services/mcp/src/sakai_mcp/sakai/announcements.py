"""Authorized announcement reads and single-attempt creation."""

from typing import Any

from mcp.server.auth.provider import AccessToken

from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.courses import list_result
from sakai_mcp.sakai.paths import segment
from sakai_mcp.sakai.transport import SakaiTransport


class AnnouncementOperations:
    def __init__(self, transport: SakaiTransport) -> None:
        self.transport = transport
        self.settings = transport.settings

    async def get_course_announcements(
        self, principal: AccessToken, course_id: str
    ) -> list[dict[str, Any]]:
        path = f"/api/mcp/v1/courses/{segment(course_id)}/announcements"
        return list_result(
            await self.transport.request("GET", path, principal), "announcements"
        )

    async def create_course_announcement(
        self, principal: AccessToken, course_id: str, title: str, body: str
    ) -> dict[str, Any]:
        if (
            not title.strip()
            or len(title) > 200
            or not body.strip()
            or len(body) > 10_000
        ):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        path = f"/api/mcp/v1/courses/{segment(course_id)}/announcements"
        result = await self.transport.request(
            "POST", path, principal, {"title": title, "body": body}
        )
        announcement = result.get("announcement")
        if not isinstance(announcement, dict) or not isinstance(
            announcement.get("id"), str
        ):
            raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME)
        return announcement
