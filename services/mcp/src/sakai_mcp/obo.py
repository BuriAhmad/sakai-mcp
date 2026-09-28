"""Certificate-backed MSAL OBO exchange and independent downstream validation."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jwt
import msal  # type: ignore[import-untyped]
import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from jwt import PyJWKClient, PyJWKClientConnectionError
from mcp.server.auth.provider import AccessToken

from sakai_mcp.auth import EntraTokenVerifier
from sakai_mcp.config import Settings


class OBOError(Exception):
    """Sanitized base class for OBO failures."""


class InvalidUpstreamToken(OBOError):
    pass


class ExchangeUnavailable(OBOError):
    pass


class InvalidDownstreamToken(OBOError):
    pass


@dataclass(frozen=True)
class CredentialFiles:
    private_key: Path
    certificate: Path


@dataclass(frozen=True)
class DownstreamToken:
    token: str
    tenant_id: str
    object_id: str
    sakai_eid: str
    expires_at: int


class _TimedHttpClient:
    def __init__(self, connect_timeout: float, read_timeout: float) -> None:
        self._session = requests.Session()
        self._timeout = (connect_timeout, read_timeout)

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self._timeout)
        return self._session.get(url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        kwargs.setdefault("timeout", self._timeout)
        return self._session.post(url, **kwargs)


class OBOProvider:
    """Exchange only verified MCP tokens for a distinct user-delegated Sakai token."""

    def __init__(
        self,
        settings: Settings,
        inbound_verifier: EntraTokenVerifier,
        credentials: CredentialFiles | None = None,
        exchange: Callable[[str, list[str]], dict[str, Any]] | None = None,
        downstream_signing_key: Callable[[str], Any] | None = None,
    ) -> None:
        self.settings = settings
        self.inbound_verifier = inbound_verifier
        if exchange is None:
            if credentials is None:
                raise ValueError("OBO credential files are required")
            certificate = credentials.certificate.read_bytes()
            private_key = credentials.private_key.read_text()
            thumbprint = x509.load_pem_x509_certificate(certificate).fingerprint(hashes.SHA1()).hex()
            app = msal.ConfidentialClientApplication(
                str(settings.mcp_resource_client_id),
                authority=f"https://login.microsoftonline.com/{settings.entra_tenant_id}",
                client_credential={
                    "private_key": private_key,
                    "thumbprint": thumbprint,
                    "public_certificate": certificate.decode(),
                },
                http_client=_TimedHttpClient(settings.http_connect_timeout, settings.http_read_timeout),
            )
            exchange = lambda assertion, scopes: app.acquire_token_on_behalf_of(assertion, scopes)
        self._exchange = exchange
        if downstream_signing_key is None:
            keys = PyJWKClient(str(settings.mcp_jwks_uri), timeout=settings.http_connect_timeout)
            downstream_signing_key = lambda token: keys.get_signing_key_from_jwt(token).key
        self._downstream_signing_key = downstream_signing_key

    async def acquire(self, upstream: AccessToken) -> DownstreamToken:
        verified = await asyncio.to_thread(self.inbound_verifier.verify, upstream.token)
        if verified is None:
            raise InvalidUpstreamToken("Invalid MCP token")
        principal, _ = verified
        if (
            upstream.resource != str(self.settings.mcp_public_url).rstrip("/")
            or self.settings.mcp_required_scope not in upstream.scopes
            or upstream.claims is None
            or upstream.claims.get("tid") != principal.tenant_id
            or upstream.claims.get("oid") != principal.object_id
        ):
            raise InvalidUpstreamToken("MCP principal mismatch")
        try:
            result = await asyncio.to_thread(
                self._exchange,
                upstream.token,
                [f"{self.settings.sakai_audience}/{self.settings.sakai_downstream_scope}"],
            )
        except Exception:  # noqa: BLE001 - MSAL/transport exceptions must be sanitized here.
            raise ExchangeUnavailable("OBO exchange unavailable") from None
        downstream = result.get("access_token") if isinstance(result, dict) else None
        if not isinstance(downstream, str) or not downstream:
            raise ExchangeUnavailable("OBO exchange did not issue a token")
        return await asyncio.to_thread(self._validate_downstream, downstream, principal.tenant_id, principal.object_id)

    def _validate_downstream(self, token: str, tenant: str, object_id: str) -> DownstreamToken:
        if len(token) > 16_384:
            raise InvalidDownstreamToken("Invalid Sakai token")
        try:
            claims = jwt.decode(
                token,
                key=self._downstream_signing_key(token),
                algorithms=["RS256"],
                audience=self.settings.sakai_audience,
                issuer=str(self.settings.sakai_issuer),
                options={"require": ["exp", "nbf", "iss", "aud", "tid", "oid", "scp"]},
                leeway=60,
            )
            scope_claim = claims["scp"]
            if not isinstance(scope_claim, str):
                raise InvalidDownstreamToken("Invalid Sakai token")
            scopes = scope_claim.split()
            eid_values = claims[self.settings.institutional_id_claim]
            if (
                claims["aud"] != self.settings.sakai_audience
                or claims["tid"] != tenant
                or claims["oid"] != object_id
                or self.settings.sakai_downstream_scope not in scopes
                or not isinstance(eid_values, list)
                or len(eid_values) != 1
                or not isinstance(eid_values[0], str)
                or not eid_values[0].strip()
                or len(eid_values[0]) > 128
                or any(ord(char) < 32 or ord(char) == 127 for char in eid_values[0])
            ):
                raise InvalidDownstreamToken("Invalid Sakai token")
        except (PyJWKClientConnectionError, OSError):
            raise ExchangeUnavailable("Sakai signing keys unavailable") from None
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            raise InvalidDownstreamToken("Invalid Sakai token") from None
        return DownstreamToken(token, tenant, object_id, eid_values[0], claims["exp"])
