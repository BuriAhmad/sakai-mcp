"""Action-specific EntityBroker reads; responses are observations, not authority."""

from mcp.server.auth.provider import AccessToken

from sakai_mcp.contracts.existing_api import (
    CurrentUser,
    SiteDetail,
    parse,
    user_permissions,
)
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.existing_transport import ExistingApiTransport
from sakai_mcp.sakai.operations import CURRENT_SITE, CURRENT_USER, USER_PERMISSIONS


class EntityBroker:
    def __init__(self, transport: ExistingApiTransport) -> None:
        self.transport = transport

    async def current_user(self, principal: AccessToken) -> CurrentUser:
        return parse(CurrentUser, await self.transport.json(CURRENT_USER, principal))

    async def site(self, principal: AccessToken, site: str) -> SiteDetail:
        result = parse(
            SiteDetail,
            await self.transport.json(
                CURRENT_SITE, principal, parameters={"site": site}
            ),
        )
        if result.id != site:
            raise SakaiError(ErrorCode.CONFLICT)
        return result

    async def user_permissions(
        self, principal: AccessToken, site: str
    ) -> frozenset[str]:
        return user_permissions(
            await self.transport.json(
                USER_PERMISSIONS, principal, parameters={"site": site}
            )
        )
