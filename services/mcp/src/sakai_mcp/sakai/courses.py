"""Course discovery and the acting user's released grades."""

from typing import Any

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts.existing_api import course_fields
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.browser_transport import BrowserTransport
from sakai_mcp.sakai.existing_transport import ExistingApiTransport
from sakai_mcp.sakai.operations import SITES
from sakai_mcp.sakai.transport import SakaiTransport
from sakai_mcp.workflows.access import AccessObservations
from sakai_mcp.workflows.own_grades import OwnGradeReads


def list_result(result: dict[str, Any], key: str) -> list[dict[str, Any]]:
    rows = result.get(key)
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    return rows


class CourseOperations:
    def __init__(
        self,
        transport: SakaiTransport,
        existing: ExistingApiTransport,
        browser: BrowserTransport,
    ) -> None:
        self.transport = transport
        self.settings = transport.settings
        self.existing = existing
        self.access = AccessObservations(existing)
        self.own_grades = OwnGradeReads(existing, browser)

    async def list_my_courses(self, principal: AccessToken) -> list[dict[str, Any]]:
        actor = await self.access.actor(principal)
        observed = await self.existing.observe_json(SITES, principal)
        actor.require_same(observed)
        visible = []
        for row in course_fields(observed.value):
            try:
                await self.access.course(principal, actor, row["id"])
            except SakaiError as error:
                if error.code in {ErrorCode.FORBIDDEN, ErrorCode.NOT_FOUND}:
                    continue
                raise
            visible.append(row)
            if len(visible) == 500:
                break
        return visible

    async def get_my_grades(
        self, principal: AccessToken, course_id: str
    ) -> list[dict[str, Any]]:
        return await self.own_grades.read(principal, course_id)
