"""Bounded existing-interface transport used by the default course-list facade.

Native auth/context and domain authorization require separate live acceptance.
No password login, cookie/session reuse, redirects or caller-selected URLs.
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
from mcp.server.auth.provider import AccessToken

from sakai_mcp.audit import current_request_id
from sakai_mcp.config import Settings
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.operations import OPERATIONS, Effect, Encoding, Operation
from sakai_mcp.security.obo import ExchangeUnavailable, OBOError, OBOProvider


@dataclass(frozen=True)
class ContentBytes:
    data: bytes
    mime_type: str
    sha256: str


@dataclass(frozen=True, repr=False)
class TokenIdentity:
    tenant_id: str
    object_id: str
    sakai_eid: str


@dataclass(frozen=True, repr=False)
class JsonObservation:
    value: Any
    identity: TokenIdentity


class ExistingApiTransport:
    def __init__(
        self,
        settings: Settings,
        obo: OBOProvider,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.obo = obo
        self._origin = str(settings.sakai_base_url).rstrip("/")
        self._owns_http = http is None
        self._http = http or httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=settings.http_connect_timeout,
                read=settings.http_read_timeout,
                write=settings.http_read_timeout,
                pool=settings.http_connect_timeout,
            ),
            follow_redirects=False,
            trust_env=False,
        )
        self._streams = asyncio.Semaphore(2)

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def json(
        self,
        op: Operation,
        principal: AccessToken,
        *,
        parameters: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
    ) -> Any:
        return (
            await self.observe_json(op, principal, parameters=parameters, query=query)
        ).value

    async def observe_json(
        self,
        op: Operation,
        principal: AccessToken,
        *,
        parameters: dict[str, str] | None = None,
        query: dict[str, str] | None = None,
    ) -> JsonObservation:
        if op.encoding != Encoding.JSON:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        data, _, identity = await self._read(op, principal, parameters, query)
        try:
            value = json.loads(
                data.decode("utf-8-sig"),
                parse_constant=_invalid_constant,
                object_pairs_hook=_unique_keys,
            )
            return JsonObservation(value, identity)
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise SakaiError(ErrorCode.INTERNAL_ERROR) from None

    async def grade_form(
        self, principal: AccessToken, values: dict[str, str]
    ) -> JsonObservation:
        """One source-defined existing action. Caller journals before invoking."""
        from sakai_mcp.sakai.operations import SET_GRADE

        body = urlencode(values).encode()
        if len(body) > 60_000:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        data, _, identity = await self._read(
            SET_GRADE, principal, None, None, body=body
        )
        try:
            return JsonObservation(
                json.loads(
                    data.decode("utf-8-sig"),
                    parse_constant=_invalid_constant,
                    object_pairs_hook=_unique_keys,
                ),
                identity,
            )
        except (ValueError, UnicodeDecodeError, RecursionError):
            raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME) from None

    async def content(self, principal: AccessToken, reference: str) -> ContentBytes:
        """Caller must first select ref from currently authorized source evidence."""
        from sakai_mcp.sakai.operations import CONTENT

        async with self._streams:
            data, headers, _ = await self._read(
                CONTENT, principal, {"resource": reference}, None
            )
        return ContentBytes(
            data,
            headers.get("content-type", "application/octet-stream"),
            hashlib.sha256(data).hexdigest(),
        )

    async def _read(
        self,
        op: Operation,
        principal: AccessToken,
        parameters: dict[str, str] | None,
        query: dict[str, str] | None,
        *,
        body: bytes | None = None,
    ) -> tuple[bytes, httpx.Headers, TokenIdentity]:
        if OPERATIONS.get(op.name) is not op:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        academic = op.effect == Effect.WRITE
        if op.blocked_reason or (academic and (op.name != "set-grade" or body is None)):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if not academic and body is not None:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        path = op.path(parameters, query)
        try:
            delegated = await self.obo.acquire(principal)
        except ExchangeUnavailable:
            raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE) from None
        except OBOError:
            raise SakaiError(ErrorCode.UNAUTHENTICATED) from None
        accept = "application/json" if op.encoding == Encoding.JSON else "*/*"
        for attempt in range(op.attempts):
            response = None
            try:
                async with asyncio.timeout(
                    self.settings.http_read_timeout
                    + self.settings.http_connect_timeout
                    + 5
                ):
                    # A direct Request deliberately bypasses client default cookies,
                    # headers, auth and base_url, including for injected test clients.
                    request = httpx.Request(
                        op.method,
                        self._origin + path,
                        headers={
                            "Authorization": f"Bearer {delegated.token}",
                            "X-Correlation-ID": current_request_id(),
                            "Accept": accept,
                            "Accept-Encoding": "identity",
                            **(
                                {
                                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
                                }
                                if body is not None
                                else {}
                            ),
                        },
                        content=body,
                    )
                    response = await self._http.send(
                        request, stream=True, follow_redirects=False, auth=None
                    )
                    if academic and response.status_code not in {
                        200,
                        400,
                        401,
                        403,
                        404,
                        422,
                        429,
                    }:
                        raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME)
                    self._status(response.status_code)
                    encoding = response.headers.get(
                        "content-encoding", "identity"
                    ).lower()
                    if encoding != "identity":
                        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                    media_type = (
                        response.headers.get("content-type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                    )
                    if (
                        op.encoding == Encoding.JSON
                        and media_type != "application/json"
                    ):
                        raise SakaiError(ErrorCode.INTERNAL_ERROR)
                    length = response.headers.get("content-length")
                    if length is not None and (
                        not length.isascii() or not length.isdecimal()
                    ):
                        raise SakaiError(ErrorCode.INTERNAL_ERROR)
                    if length is not None and int(length) > op.max_bytes:
                        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(chunks) + len(chunk) > op.max_bytes:
                            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                        chunks.extend(chunk)
                    if length is not None and len(chunks) != int(length):
                        raise SakaiError(ErrorCode.CONFLICT)
                    # Return no cookies, session headers, URLs or arbitrary raw headers.
                    return (
                        bytes(chunks),
                        httpx.Headers(
                            {
                                "content-type": response.headers.get(
                                    "content-type", "application/octet-stream"
                                )
                            }
                        ),
                        TokenIdentity(
                            delegated.tenant_id,
                            delegated.object_id,
                            delegated.sakai_eid,
                        ),
                    )
            except SakaiError as error:
                if academic:
                    if response is not None and response.status_code in {
                        400,
                        401,
                        403,
                        404,
                        422,
                        429,
                    }:
                        raise
                    raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME) from None
                if (
                    error.code != ErrorCode.DEPENDENCY_UNAVAILABLE
                    or attempt + 1 == op.attempts
                ):
                    raise
            except httpx.DecodingError:
                raise SakaiError(
                    ErrorCode.AMBIGUOUS_WRITE_OUTCOME
                    if academic
                    else ErrorCode.INTERNAL_ERROR
                ) from None
            except (httpx.HTTPError, TimeoutError):
                if academic:
                    raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME) from None
                if attempt + 1 == op.attempts:
                    raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE) from None
            finally:
                if response is not None:
                    await response.aclose()
            await asyncio.sleep(0.05 * (attempt + 1))
        raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE)

    @staticmethod
    def _status(status: int) -> None:
        if 200 <= status < 300:
            return
        codes = {
            400: ErrorCode.VALIDATION_ERROR,
            401: ErrorCode.UNAUTHENTICATED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            409: ErrorCode.CONFLICT,
            410: ErrorCode.NOT_FOUND,
            422: ErrorCode.VALIDATION_ERROR,
            429: ErrorCode.RATE_LIMITED,
            501: ErrorCode.UNSUPPORTED_CAPABILITY,
            502: ErrorCode.DEPENDENCY_UNAVAILABLE,
            503: ErrorCode.DEPENDENCY_UNAVAILABLE,
            504: ErrorCode.DEPENDENCY_UNAVAILABLE,
        }
        # Redirects must never silently acquire a credential at another location.
        raise SakaiError(codes.get(status, ErrorCode.INTERNAL_ERROR))


def _invalid_constant(_: str) -> None:
    raise ValueError("Invalid JSON constant")


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result
