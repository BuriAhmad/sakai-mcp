"""Course discovery and the acting user's released grades."""

from typing import Any

from mcp.server.auth.provider import AccessToken

from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.paths import segment
from sakai_mcp.sakai.transport import SakaiTransport


def list_result(result: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = result.get(key)
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    return rows


class CourseOperations:
    def __init__(self, transport: SakaiTransport) -> None:
        self.transport = transport
        self.settings = transport.settings

    async def list_my_courses(self, principal: AccessToken) -> list[dict[str, Any]]:
        return list_result(
            await self.transport.request("GET", "/api/mcp/v1/courses", principal),
            "courses",
        )

    async def get_my_grades(
        self, principal: AccessToken, course_id: str
    ) -> list[dict[str, Any]]:
        path = f"/api/mcp/v1/courses/{segment(course_id)}/grades/me"
        return list_result(
            await self.transport.request("GET", path, principal), "grades"
        )
