"""Own one shared transport and expose typed Sakai operation groups."""

import httpx

from sakai_mcp.config import Settings
from sakai_mcp.sakai.announcements import AnnouncementOperations
from sakai_mcp.sakai.assignments import AssignmentOperations
from sakai_mcp.sakai.courses import CourseOperations
from sakai_mcp.sakai.grading import GradingOperations
from sakai_mcp.sakai.transport import SakaiTransport
from sakai_mcp.security.obo import OBOProvider


class SakaiClient:
    def __init__(
        self,
        settings: Settings,
        obo: OBOProvider,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.transport = SakaiTransport(settings, obo, http)
        self.courses = CourseOperations(self.transport)
        self.announcements = AnnouncementOperations(self.transport)
        self.assignments = AssignmentOperations(self.transport)
        self.grading = GradingOperations(self.transport)

    async def aclose(self) -> None:
        await self.transport.aclose()
