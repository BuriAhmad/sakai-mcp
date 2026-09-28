import asyncio

import httpx
import pytest
from mcp.server.auth.provider import AccessToken

from sakai_mcp.obo import DownstreamToken
from sakai_mcp.sakai_client import ErrorCode, SakaiClient, SakaiError
from tests.helpers import settings


class FakeOBO:
    calls = 0

    async def acquire(self, _: AccessToken) -> DownstreamToken:
        self.calls += 1
        return DownstreamToken("synthetic-token", "tenant", "person", "synthetic-eid", 2_000_000_000)


def principal():
    return AccessToken(token="upstream", client_id="test-client", scopes=["mcp.access"])


def client(handler):
    transport = httpx.MockTransport(handler)
    return SakaiClient(settings(), FakeOBO(), httpx.AsyncClient(transport=transport))


def test_read_uses_fixed_host_delegated_token_and_correlation_id():
    def handler(request):
        assert request.url.host == "sakai.example.test"
        assert request.url.path == "/api/mcp/v1/courses"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        assert request.headers["x-correlation-id"]
        return httpx.Response(200, json={"courses": [{"id": "course-a", "title": "Field Methods"}]})

    rows = asyncio.run(client(handler).list_my_courses(principal()))
    assert rows == [{"id": "course-a", "title": "Field Methods"}]


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, ErrorCode.UNAUTHENTICATED),
        (403, ErrorCode.FORBIDDEN),
        (404, ErrorCode.NOT_FOUND),
        (409, ErrorCode.CONFLICT),
        (429, ErrorCode.RATE_LIMITED),
    ],
)
def test_status_mapping(status, code):
    with pytest.raises(SakaiError) as error:
        asyncio.run(client(lambda _: httpx.Response(status)).get_my_grades(principal(), "course-a"))
    assert error.value.code == code


def test_transient_read_is_retried_with_bounded_attempts():
    attempts = 0

    def handler(_):
        nonlocal attempts
        attempts += 1
        return httpx.Response(503 if attempts < 3 else 200, json={"announcements": []})

    assert asyncio.run(client(handler).get_course_announcements(principal(), "course-a")) == []
    assert attempts == 3


def test_create_succeeds_once_and_does_not_accept_destination_from_arguments():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        assert request.url.host == "sakai.example.test"
        assert request.method == "POST"
        assert request.url.path.endswith("/courses/course-a/announcements")
        return httpx.Response(201, json={"announcement": {"id": "new-1", "courseId": "course-a"}})

    result = asyncio.run(client(handler).create_course_announcement(principal(), "course-a", "Lab update", "Bring notebooks."))
    assert result["id"] == "new-1"
    assert calls == 1


@pytest.mark.parametrize("failure", ["read-timeout", "server-error", "bad-json"])
def test_ambiguous_create_is_never_retried(failure):
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        if failure == "read-timeout":
            raise httpx.ReadTimeout("synthetic timeout", request=request)
        if failure == "server-error":
            return httpx.Response(503)
        return httpx.Response(201, text="invalid JSON")

    with pytest.raises(SakaiError) as error:
        asyncio.run(client(handler).create_course_announcement(principal(), "course-a", "Lab update", "Bring notebooks."))
    assert error.value.code == ErrorCode.AMBIGUOUS_WRITE_OUTCOME
    assert calls == 1


def test_preconnect_create_failure_is_dependency_unavailable_without_retry():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        raise httpx.ConnectTimeout("synthetic timeout", request=request)

    with pytest.raises(SakaiError) as error:
        asyncio.run(client(handler).create_course_announcement(principal(), "course-a", "Lab update", "Bring notebooks."))
    assert error.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE
    assert calls == 1


def test_committed_create_with_lost_response_is_reconciled_by_read_without_replay():
    announcements = []
    post_calls = 0

    def handler(request):
        nonlocal post_calls
        if request.method == "POST":
            post_calls += 1
            announcements.append({"id": "created-once", "title": "Synthetic check"})
            raise httpx.ReadTimeout("synthetic response lost after commit", request=request)
        assert request.method == "GET"
        return httpx.Response(200, json={"announcements": announcements})

    adapter = client(handler)
    with pytest.raises(SakaiError) as error:
        asyncio.run(adapter.create_course_announcement(principal(), "course-a", "Synthetic check", "Synthetic body"))
    assert error.value.code == ErrorCode.AMBIGUOUS_WRITE_OUTCOME
    visible = asyncio.run(adapter.get_course_announcements(principal(), "course-a"))
    assert [row["id"] for row in visible] == ["created-once"]
    assert post_calls == 1


def test_invalid_course_id_and_oversize_response_are_rejected():
    with pytest.raises(SakaiError) as error:
        asyncio.run(client(lambda _: httpx.Response(200, json={"grades": []})).get_my_grades(principal(), ""))
    assert error.value.code == ErrorCode.VALIDATION_ERROR
    with pytest.raises(SakaiError) as error:
        asyncio.run(client(lambda _: httpx.Response(200, content=b"x" * 1_000_001)).list_my_courses(principal()))
    assert error.value.code == ErrorCode.INTERNAL_ERROR


@pytest.mark.parametrize("failure", ["connect", "read", "rate-limit", "malformed", "oversize"])
def test_read_failures_are_bounded_and_recover_after_dependency_restoration(failure):
    attempts = 0
    healthy = False

    def handler(request):
        nonlocal attempts
        attempts += 1
        if healthy:
            return httpx.Response(200, json={"courses": [{"id": "course-a"}]})
        if failure == "connect":
            raise httpx.ConnectTimeout("private Sakai detail", request=request)
        if failure == "read":
            raise httpx.ReadTimeout("private Sakai detail", request=request)
        if failure == "rate-limit":
            return httpx.Response(429, text="private Sakai detail")
        if failure == "malformed":
            return httpx.Response(200, text="private Sakai detail")
        return httpx.Response(200, content=b"x" * 1_000_001)

    adapter = client(handler)
    with pytest.raises(SakaiError) as error:
        asyncio.run(adapter.list_my_courses(principal()))
    expected = {
        "connect": ErrorCode.DEPENDENCY_UNAVAILABLE,
        "read": ErrorCode.DEPENDENCY_UNAVAILABLE,
        "rate-limit": ErrorCode.RATE_LIMITED,
        "malformed": ErrorCode.INTERNAL_ERROR,
        "oversize": ErrorCode.INTERNAL_ERROR,
    }[failure]
    assert error.value.code == expected
    assert "private" not in str(error.value)
    assert attempts == (3 if failure in ("connect", "read") else 1)
    healthy = True
    assert asyncio.run(adapter.list_my_courses(principal())) == [{"id": "course-a"}]
    assert attempts == (4 if failure in ("connect", "read") else 2)


def test_declared_oversize_body_is_rejected_before_stream_consumption():
    def handler(_):
        return httpx.Response(200, headers={"content-length": "1000001"}, content=b"private body")

    with pytest.raises(SakaiError) as error:
        asyncio.run(client(handler).list_my_courses(principal()))
    assert error.value.code == ErrorCode.INTERNAL_ERROR
