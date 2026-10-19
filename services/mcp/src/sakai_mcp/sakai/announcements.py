"""Authorized announcement reads and single-attempt creation."""

from typing import Any

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts.announcements import (
    LOOKBACK_DAYS,
    OBSERVATION_CAP,
    announcement_rows,
)
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.existing_transport import ExistingApiTransport
from sakai_mcp.sakai.operations import ANNOUNCEMENTS
from sakai_mcp.sakai.transport import SakaiTransport
from sakai_mcp.workflows.access import AccessObservations
from sakai_mcp.workflows.announcements import AnnouncementCreation


class AnnouncementOperations:
    def __init__(
        self,
        transport: SakaiTransport,
        existing: ExistingApiTransport,
        creation: AnnouncementCreation,
    ) -> None:
        self.transport = transport
        self.settings = transport.settings
        self.existing = existing
        self.access = AccessObservations(existing)
        self.creation = creation

    async def get_course_announcements(
        self, principal: AccessToken, course_id: str
    ) -> list[dict[str, Any]]:
        actor = await self.access.actor(principal)
        await self.access.course(principal, actor, course_id)
        observed = await self.existing.observe_json(
            ANNOUNCEMENTS,
            principal,
            parameters={"site": course_id},
            query={"n": str(OBSERVATION_CAP), "d": str(LOOKBACK_DAYS), "a": "0"},
        )
        actor.require_same(observed)
        # Native visibility is authoritative. This is a bounded provider
        # observation: a short response does not certify channel completeness.
        return announcement_rows(observed.value, course_id)

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
        return await self.creation.create(principal, course_id, title, body)
