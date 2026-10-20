"""Bounded existing Portal HTTP conversations; no generic URL proxy or JS runtime."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlencode

import httpx
from mcp.server.auth.provider import AccessToken

from sakai_mcp.audit import current_request_id
from sakai_mcp.config import Settings
from sakai_mcp.contracts.native_forms import NativeForm, native_url
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.existing_transport import ExistingApiTransport, TokenIdentity
from sakai_mcp.security.obo import ExchangeUnavailable, OBOError, OBOProvider
from sakai_mcp.security.sakai_flow import SakaiFlow


@dataclass(frozen=True)
class NativePage:
    url: str = field(repr=False)
    data: bytes = field(repr=False)
    content_type: str


class BrowserTransport:
    def __init__(
        self,
        settings: Settings,
        obo: OBOProvider,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings, self.obo = settings, obo
        self.origin = str(settings.sakai_base_url).rstrip("/")
        self._owns_http = http is None
        self._http = http or httpx.AsyncClient(
            timeout=httpx.Timeout(
                settings.http_read_timeout, connect=settings.http_connect_timeout
            ),
            follow_redirects=False,
            trust_env=False,
        )

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    @asynccontextmanager
    async def conversation(
        self,
        principal: AccessToken,
        placement: str,
        *,
        identity: TokenIdentity | None = None,
    ) -> AsyncIterator[NativeConversation]:
        flow = NativeConversation(self, principal, placement, identity)
        try:
            yield flow
        finally:
            await flow.aclose()


class NativeConversation:
    def __init__(
        self,
        transport: BrowserTransport,
        principal: AccessToken,
        placement: str,
        identity: TokenIdentity | None = None,
    ) -> None:
        self.transport, self.principal, self.placement = transport, principal, placement
        self.identity = identity
        self._state = SakaiFlow()
        self._url = native_url(
            transport.origin, transport.origin, f"/portal/tool/{placement}", placement
        )

    async def navigate(self, rendered_url: str | None = None) -> NativePage:
        # GET links can change native tool/helper state. Never replay automatically.
        async with self._state.lock:
            target = native_url(
                self.transport.origin,
                self._url,
                rendered_url or self._url,
                self.placement,
            )
            return await self._exchange("GET", target, None, academic=False)

    async def submit(
        self, form: NativeForm, changes: dict[str, str | list[str]], *, academic: bool
    ) -> NativePage:
        """Academic callers must durably journal their approved intent before this call."""
        async with self._state.lock:
            target = native_url(
                self.transport.origin, self._url, form.action, self.placement
            )
            return await self._exchange(
                "POST",
                target,
                urlencode(form.values(changes)).encode(),
                academic=academic,
            )

    async def _exchange(
        self,
        method: Literal["GET", "POST"],
        target: str,
        body: bytes | None,
        *,
        academic: bool,
    ) -> NativePage:
        previous_mutation_response = False
        for _ in range(5):
            self._state.next_step()
            try:
                delegated = await self.transport.obo.acquire(self.principal)
                if self.identity is not None and self.identity != TokenIdentity(
                    delegated.tenant_id, delegated.object_id, delegated.sakai_eid
                ):
                    raise SakaiError(ErrorCode.UNAUTHENTICATED)
            except ExchangeUnavailable:
                raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE) from None
            except OBOError:
                raise SakaiError(ErrorCode.UNAUTHENTICATED) from None
            response = None
            try:
                async with asyncio.timeout(
                    self.transport.settings.http_connect_timeout
                    + self.transport.settings.http_read_timeout
                    + 5
                ):
                    headers = {
                        "Authorization": f"Bearer {delegated.token}",
                        "X-Correlation-ID": current_request_id(),
                        "Accept": "text/html,application/xhtml+xml,application/xml,text/xml,application/json",
                        "Accept-Encoding": "identity",
                        **self._state.headers(),
                    }
                    if body is not None:
                        headers["Content-Type"] = (
                            "application/x-www-form-urlencoded; charset=UTF-8"
                        )
                    self._state.started = True
                    response = await self.transport._http.send(
                        httpx.Request(method, target, headers=headers, content=body),
                        stream=True,
                        follow_redirects=False,
                        auth=None,
                    )
                    if (
                        academic
                        and method == "POST"
                        and response.status_code not in {400, 401, 403, 404, 422, 429}
                    ):
                        previous_mutation_response = True
                    if response.status_code in {301, 302, 303}:
                        location = response.headers.get("location")
                        if not location:
                            raise SakaiError(ErrorCode.INTERNAL_ERROR)
                        target = native_url(
                            self.transport.origin, target, location, self.placement
                        )
                        # Follow only as a new GET, never replay a submitted body.
                        method, body = "GET", None
                        continue
                    if response.status_code in {307, 308}:
                        raise SakaiError(ErrorCode.INTERNAL_ERROR)
                    ExistingApiTransport._status(response.status_code)
                    mime = (
                        response.headers.get("content-type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                    )
                    if (
                        mime
                        not in {
                            "text/html",
                            "application/xhtml+xml",
                            "application/xml",
                            "text/xml",
                            "application/json",
                        }
                        or response.headers.get("content-encoding", "identity").lower()
                        != "identity"
                    ):
                        raise SakaiError(ErrorCode.INTERNAL_ERROR)
                    length = response.headers.get("content-length")
                    if length is not None and (
                        not length.isascii()
                        or not length.isdecimal()
                        or int(length) > 1_000_000
                    ):
                        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                    chunks = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(chunks) + len(chunk) > 1_000_000:
                            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
                        chunks.extend(chunk)
                    if length is not None and int(length) != len(chunks):
                        raise SakaiError(ErrorCode.CONFLICT)
                    self._url = target
                    return NativePage(target, bytes(chunks), mime)
            except httpx.ConnectError:
                raise SakaiError(
                    ErrorCode.AMBIGUOUS_WRITE_OUTCOME
                    if previous_mutation_response
                    else ErrorCode.DEPENDENCY_UNAVAILABLE
                ) from None
            except httpx.ConnectTimeout:
                raise SakaiError(
                    ErrorCode.AMBIGUOUS_WRITE_OUTCOME
                    if previous_mutation_response
                    else ErrorCode.DEPENDENCY_UNAVAILABLE
                ) from None
            except (httpx.HTTPError, TimeoutError):
                raise SakaiError(
                    ErrorCode.AMBIGUOUS_WRITE_OUTCOME
                    if academic
                    else ErrorCode.DEPENDENCY_UNAVAILABLE
                ) from None
            except SakaiError as error:
                if academic and (
                    previous_mutation_response
                    or error.code
                    not in {
                        ErrorCode.UNAUTHENTICATED,
                        ErrorCode.FORBIDDEN,
                        ErrorCode.NOT_FOUND,
                        ErrorCode.VALIDATION_ERROR,
                        ErrorCode.RATE_LIMITED,
                    }
                ):
                    raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME) from None
                raise
            finally:
                if response is not None:
                    await response.aclose()
        raise SakaiError(
            ErrorCode.AMBIGUOUS_WRITE_OUTCOME if academic else ErrorCode.INTERNAL_ERROR
        )

    async def aclose(self) -> None:
        async with self._state.lock:
            await self._close()

    async def _close(self) -> None:
        if self._state.closed:
            return
        self._state.closed = True
        if not self._state.started:
            return
        try:
            async with asyncio.timeout(5):
                delegated = await self.transport.obo.acquire(self.principal)
                if self.identity is not None and self.identity != TokenIdentity(
                    delegated.tenant_id, delegated.object_id, delegated.sakai_eid
                ):
                    self._state.cleanup_failed = True
                    return
                # Auth-only end marker on an existing safe read. No new logout route.
                request = httpx.Request(
                    "GET",
                    self.transport.origin + "/direct/user/current.json",
                    headers={
                        "Authorization": f"Bearer {delegated.token}",
                        "Accept": "application/json",
                        "X-Correlation-ID": current_request_id(),
                        **self._state.headers(end=True),
                    },
                )
                response = await self.transport._http.send(
                    request, stream=True, follow_redirects=False, auth=None
                )
                try:
                    if response.status_code not in {200, 410}:
                        self._state.cleanup_failed = True
                finally:
                    await response.aclose()
        except (httpx.HTTPError, TimeoutError, OBOError):
            # Native maximum age/inactivity remains the fallback; no login retry.
            self._state.cleanup_failed = True
