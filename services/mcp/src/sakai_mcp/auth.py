"""Inbound delegated Entra access-token verification for MCP requests."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import PyJWKClient
from mcp.server.auth.provider import AccessToken

from sakai_mcp.config import Settings


@dataclass(frozen=True)
class Principal:
    tenant_id: str
    object_id: str
    scopes: frozenset[str]
    client_id: str


class EntraTokenVerifier:
    """Use only trusted settings for key discovery and audience selection."""

    def __init__(
        self,
        settings: Settings,
        signing_key: Callable[[str], Any] | None = None,
    ) -> None:
        self.settings = settings
        if signing_key is None:
            keys = PyJWKClient(str(settings.mcp_jwks_uri), timeout=settings.http_connect_timeout)
            signing_key = lambda token: keys.get_signing_key_from_jwt(token).key
        self._signing_key = signing_key

    def verify(self, token: str) -> tuple[Principal, dict[str, Any]] | None:
        if not token or len(token) > 16_384:
            return None
        try:
            claims = jwt.decode(
                token,
                key=self._signing_key(token),
                algorithms=["RS256"],
                audience=self.settings.mcp_audience,
                issuer=str(self.settings.mcp_issuer),
                options={"require": ["exp", "nbf", "iss", "aud", "tid", "oid", "scp"]},
                leeway=60,
            )
        except (jwt.PyJWTError, ValueError, TypeError, OSError):
            return None
        if claims.get("aud") != self.settings.mcp_audience:
            return None
        tenant = claims.get("tid")
        object_id = claims.get("oid")
        scope_claim = claims.get("scp")
        client_id = claims.get("azp") or claims.get("appid")
        if (
            tenant != str(self.settings.entra_tenant_id)
            or not isinstance(object_id, str)
            or not object_id.strip()
            or not isinstance(scope_claim, str)
            or not isinstance(client_id, str)
            or not client_id.strip()
        ):
            return None
        scopes = frozenset(scope_claim.split())
        if self.settings.mcp_required_scope not in scopes:
            return None
        # `scp` plus a human object ID are required. App-only `roles` are never authority.
        return Principal(tenant, object_id, scopes, client_id), claims

    async def verify_token(self, token: str) -> AccessToken | None:
        result = await asyncio.to_thread(self.verify, token)
        if result is None:
            return None
        principal, claims = result
        return AccessToken(
            token=token,
            client_id=principal.client_id,
            scopes=sorted(principal.scopes),
            expires_at=claims["exp"],
            resource=str(self.settings.mcp_public_url).rstrip("/"),
            subject=f"{principal.tenant_id}:{principal.object_id}",
            claims={"tid": principal.tenant_id, "oid": principal.object_id},
        )
