"""Bounded HTTP adapter for the five narrow Sakai MCP integration routes."""

import asyncio
import json
import random
from enum import StrEnum
from typing import Any
from urllib.parse import quote

import httpx
from mcp.server.auth.provider import AccessToken

from sakai_mcp.audit import current_request_id
from sakai_mcp.config import Settings
from sakai_mcp.obo import ExchangeUnavailable, OBOError, OBOProvider


class ErrorCode(StrEnum):
    UNAUTHENTICATED = "UNAUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    DEPENDENCY_UNAVAILABLE = "DEPENDENCY_UNAVAILABLE"
    AMBIGUOUS_WRITE_OUTCOME = "AMBIGUOUS_WRITE_OUTCOME"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class SakaiError(Exception):
    def __init__(self, code: ErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


def _segment(value: str) -> str:
    if (
        not value
        or value in (".", "..")
        or len(value) > 128
        or value != value.strip()
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise SakaiError(ErrorCode.VALIDATION_ERROR)
    return quote(value, safe="")


class SakaiClient:
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

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def list_my_courses(self, principal: AccessToken) -> list[dict[str, Any]]:
        return self._list(await self._request("GET", "/api/mcp/v1/courses", principal), "courses")

    async def get_my_grades(self, principal: AccessToken, course_id: str) -> list[dict[str, Any]]:
        path = f"/api/mcp/v1/courses/{_segment(course_id)}/grades/me"
        return self._list(await self._request("GET", path, principal), "grades")

    async def get_course_announcements(self, principal: AccessToken, course_id: str) -> list[dict[str, Any]]:
        path = f"/api/mcp/v1/courses/{_segment(course_id)}/announcements"
        return self._list(await self._request("GET", path, principal), "announcements")

    async def get_course_submissions(
        self, principal: AccessToken, course_id: str, assignment_id: str
    ) -> list[dict[str, Any]]:
        path = f"/api/mcp/v1/courses/{_segment(course_id)}/assignments/{_segment(assignment_id)}/submissions"
        return self._list(await self._request("GET", path, principal), "submissions")

    async def create_course_announcement(
        self, principal: AccessToken, course_id: str, title: str, body: str
    ) -> dict[str, Any]:
        if not title.strip() or len(title) > 200 or not body.strip() or len(body) > 10_000:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        path = f"/api/mcp/v1/courses/{_segment(course_id)}/announcements"
        result = await self._request("POST", path, principal, {"title": title, "body": body})
        announcement = result.get("announcement")
        if not isinstance(announcement, dict) or not isinstance(announcement.get("id"), str):
            raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME)
        return announcement

    @staticmethod
    def _list(result: dict[str, Any], key: str) -> list[dict[str, Any]]:
        rows = result.get(key)
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise SakaiError(ErrorCode.INTERNAL_ERROR)
        return rows

    async def _request(
        self, method: str, path: str, principal: AccessToken, payload: dict[str, str] | None = None
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
                async with asyncio.timeout(self.settings.http_connect_timeout + self.settings.http_read_timeout + 5):
                    async with self._http.stream(
                        method, self._base + path, headers=headers, json=payload
                    ) as response:
                        self._raise_for_status(response.status_code, method)
                        length = response.headers.get("content-length")
                        if length and length.isdecimal() and int(length) > 1_000_000:
                            raise SakaiError(ErrorCode.INTERNAL_ERROR if method == "GET" else ErrorCode.AMBIGUOUS_WRITE_OUTCOME)
                        chunks = bytearray()
                        async for chunk in response.aiter_bytes():
                            chunks.extend(chunk)
                            if len(chunks) > 1_000_000:
                                raise SakaiError(ErrorCode.INTERNAL_ERROR if method == "GET" else ErrorCode.AMBIGUOUS_WRITE_OUTCOME)
                value = json.loads(chunks)
                if not isinstance(value, dict):
                    raise SakaiError(ErrorCode.INTERNAL_ERROR if method == "GET" else ErrorCode.AMBIGUOUS_WRITE_OUTCOME)
                return value
            except SakaiError as exc:
                if method == "GET" and exc.code == ErrorCode.DEPENDENCY_UNAVAILABLE and attempt + 1 < attempts:
                    await asyncio.sleep(random.uniform(0.05, 0.15) * (attempt + 1))
                    continue
                raise
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout):
                error = ErrorCode.DEPENDENCY_UNAVAILABLE
            except (httpx.HTTPError, TimeoutError):
                error = ErrorCode.DEPENDENCY_UNAVAILABLE if method == "GET" else ErrorCode.AMBIGUOUS_WRITE_OUTCOME
            except (json.JSONDecodeError, UnicodeDecodeError):
                error = ErrorCode.INTERNAL_ERROR if method == "GET" else ErrorCode.AMBIGUOUS_WRITE_OUTCOME
            if method == "GET" and error == ErrorCode.DEPENDENCY_UNAVAILABLE and attempt + 1 < attempts:
                await asyncio.sleep(random.uniform(0.05, 0.15) * (attempt + 1))
                continue
            raise SakaiError(error) from None
        raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE)

    @staticmethod
    def _raise_for_status(status: int, method: str) -> None:
        if 200 <= status < 300:
            return
        if method == "POST" and status >= 500:
            raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME)
        codes = {
            400: ErrorCode.VALIDATION_ERROR,
            401: ErrorCode.UNAUTHENTICATED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            409: ErrorCode.CONFLICT,
            422: ErrorCode.VALIDATION_ERROR,
            429: ErrorCode.RATE_LIMITED,
            502: ErrorCode.DEPENDENCY_UNAVAILABLE,
            503: ErrorCode.DEPENDENCY_UNAVAILABLE,
            504: ErrorCode.DEPENDENCY_UNAVAILABLE,
        }
        raise SakaiError(codes.get(status, ErrorCode.INTERNAL_ERROR))
