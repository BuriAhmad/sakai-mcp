"""Bounded fixed-origin HTTP with delegated tokens and explicit retry semantics."""

import asyncio
import hashlib
import json
import random
from typing import Any

import httpx
from mcp.server.auth.provider import AccessToken

from sakai_mcp.audit import current_request_id
from sakai_mcp.config import Settings
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.security.obo import ExchangeUnavailable, OBOError, OBOProvider


class SakaiTransport:
    def __init__(
        self,
        settings: Settings,
        obo: OBOProvider,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self.obo = obo
        self._base = str(settings.sakai_base_url).rstrip("/")
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
        self._owns_http = http is None
        self._grading_reads = asyncio.Semaphore(2)

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def _open_binary_stream(
        self, principal: AccessToken, path: str
    ) -> httpx.Response:
        response = None
        try:
            downstream = await self.obo.acquire(principal)
            request = self._http.build_request(
                "GET",
                self._base + path,
                headers={"Authorization": f"Bearer {downstream.token}"},
            )
            response = await self._http.send(request, stream=True)
            self._raise_for_status(response.status_code, "GET", unsupported=True)
            length = response.headers.get("content-length", "")
            sha = response.headers.get("x-content-sha256", "")
            if (
                not length.isdecimal()
                or int(length) > 10 * 1024 * 1024
                or len(sha) != 64
                or any(c not in "0123456789abcdef" for c in sha)
            ):
                await response.aclose()
                raise SakaiError(ErrorCode.INTERNAL_ERROR)
            return response
        except SakaiError:
            if response is not None:
                await response.aclose()
            raise
        except (httpx.HTTPError, OBOError, ExchangeUnavailable):
            if response is not None:
                await response.aclose()
            raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE) from None

    async def read_bytes(
        self, principal: AccessToken, path: str
    ) -> tuple[bytes, str, str]:
        async with self._grading_reads:
            return await self._read_binary(principal, path)

    async def _read_binary(
        self, principal: AccessToken, path: str
    ) -> tuple[bytes, str, str]:
        response = await self._open_binary_stream(principal, path)
        try:
            data = bytearray()
            async with asyncio.timeout(self.settings.http_read_timeout + 5):
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 10 * 1024 * 1024:
                        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            sha = hashlib.sha256(data).hexdigest()
            if (
                len(data) != int(response.headers["content-length"])
                or sha != response.headers["x-content-sha256"]
            ):
                raise SakaiError(ErrorCode.CONFLICT)
            return (
                bytes(data),
                response.headers.get("content-type", "application/octet-stream"),
                sha,
            )
        except (httpx.HTTPError, TimeoutError):
            raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE) from None
        finally:
            await response.aclose()

    async def request(
        self,
        method: str,
        path: str,
        principal: AccessToken,
        payload: dict[str, Any] | None = None,
        *,
        unsupported: bool = False,
    ) -> dict[str, Any]:
        try:
            delegated = await self.obo.acquire(principal)
        except ExchangeUnavailable:
            raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE) from None
        except OBOError:
            raise SakaiError(ErrorCode.UNAUTHENTICATED) from None
        headers = {
            "Authorization": f"Bearer {delegated.token}",
            "X-Correlation-ID": current_request_id(),
            "Accept": "application/json",
        }
        attempts = 3 if method == "GET" else 1
        for attempt in range(attempts):
            try:
                async with asyncio.timeout(
                    self.settings.http_connect_timeout
                    + self.settings.http_read_timeout
                    + 5
                ):
                    async with self._http.stream(
                        method, self._base + path, headers=headers, json=payload
                    ) as response:
                        self._raise_for_status(
                            response.status_code, method, unsupported=unsupported
                        )
                        length = response.headers.get("content-length")
                        if length and length.isdecimal() and int(length) > 1_000_000:
                            raise SakaiError(
                                ErrorCode.INTERNAL_ERROR
                                if method == "GET"
                                else ErrorCode.AMBIGUOUS_WRITE_OUTCOME
                            )
                        chunks = bytearray()
                        async for chunk in response.aiter_bytes():
                            chunks.extend(chunk)
                            if len(chunks) > 1_000_000:
                                raise SakaiError(
                                    ErrorCode.INTERNAL_ERROR
                                    if method == "GET"
                                    else ErrorCode.AMBIGUOUS_WRITE_OUTCOME
                                )
                value = json.loads(chunks)
                if not isinstance(value, dict):
                    raise SakaiError(
                        ErrorCode.INTERNAL_ERROR
                        if method == "GET"
                        else ErrorCode.AMBIGUOUS_WRITE_OUTCOME
                    )
                return value
            except SakaiError as exc:
                if (
                    method == "GET"
                    and exc.code == ErrorCode.DEPENDENCY_UNAVAILABLE
                    and attempt + 1 < attempts
                ):
                    await asyncio.sleep(random.uniform(0.05, 0.15) * (attempt + 1))
                    continue
                raise
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
                error = ErrorCode.DEPENDENCY_UNAVAILABLE
            except (httpx.HTTPError, TimeoutError):
                error = (
                    ErrorCode.DEPENDENCY_UNAVAILABLE
                    if method == "GET"
                    else ErrorCode.AMBIGUOUS_WRITE_OUTCOME
                )
            except (json.JSONDecodeError, UnicodeDecodeError):
                error = (
                    ErrorCode.INTERNAL_ERROR
                    if method == "GET"
                    else ErrorCode.AMBIGUOUS_WRITE_OUTCOME
                )
            if (
                method == "GET"
                and error == ErrorCode.DEPENDENCY_UNAVAILABLE
                and attempt + 1 < attempts
            ):
                await asyncio.sleep(random.uniform(0.05, 0.15) * (attempt + 1))
                continue
            raise SakaiError(error) from None
        raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE)

    @staticmethod
    def _raise_for_status(
        status: int, method: str, *, unsupported: bool = False
    ) -> None:
        if 200 <= status < 300:
            return
        if status == 501 and unsupported:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if method == "POST" and status >= 500:
            raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME)
        codes = {
            400: ErrorCode.VALIDATION_ERROR,
            401: ErrorCode.UNAUTHENTICATED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            409: ErrorCode.CONFLICT,
            410: ErrorCode.NOT_FOUND,
            422: ErrorCode.VALIDATION_ERROR,
            501: ErrorCode.UNSUPPORTED_CAPABILITY,
            429: ErrorCode.RATE_LIMITED,
            502: ErrorCode.DEPENDENCY_UNAVAILABLE,
            503: ErrorCode.DEPENDENCY_UNAVAILABLE,
            504: ErrorCode.DEPENDENCY_UNAVAILABLE,
        }
        raise SakaiError(codes.get(status, ErrorCode.INTERNAL_ERROR))
