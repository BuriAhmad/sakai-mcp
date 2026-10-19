"""Explicit existing WebAPI reads; not selected by public operation facades yet."""

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts.existing_api import Sites, parse
from sakai_mcp.sakai.existing_transport import ExistingApiTransport
from sakai_mcp.sakai.operations import SITES


class WebApi:
    def __init__(self, transport: ExistingApiTransport) -> None:
        self.transport = transport

    async def sites(self, principal: AccessToken) -> Sites:
        # Literal me; no alternate-user path or pinned-only query.
        return parse(Sites, await self.transport.json(SITES, principal))
