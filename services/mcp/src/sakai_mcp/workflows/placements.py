"""Invocation-local discovery, after native course access and actor validation."""

from dataclasses import dataclass

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts.placements import Placement, placement
from sakai_mcp.sakai.existing_transport import ExistingApiTransport
from sakai_mcp.sakai.operations import SITE_PAGES
from sakai_mcp.workflows.access import AccessObservations, CourseAccess


@dataclass(frozen=True, repr=False)
class BoundPlacement:
    access: CourseAccess
    target: Placement


class PlacementDiscovery:
    def __init__(self, transport: ExistingApiTransport) -> None:
        self.transport = transport
        self.access = AccessObservations(transport)

    async def resolve(
        self, principal: AccessToken, site: str, tool: str
    ) -> BoundPlacement:
        actor = await self.access.actor(principal)
        access = await self.access.course(principal, actor, site)
        observed = await self.transport.observe_json(
            SITE_PAGES, principal, parameters={"site": site}
        )
        actor.require_same(observed)
        target = placement(
            observed.value,
            site,
            tool,
            str(self.transport.settings.sakai_base_url).rstrip("/"),
        )
        return BoundPlacement(access, target)
