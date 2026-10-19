import asyncio

import httpx
import pytest

from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.client import SakaiClient
from sakai_mcp.sakai.paths import segment
from tests.fixtures.authentication import settings
from tests.fixtures.sakai import FakeOBO, principal


def client(handler):
    transport = httpx.MockTransport(handler)
    return SakaiClient(settings(), FakeOBO(), httpx.AsyncClient(transport=transport))


async def legacy_read(adapter, course="course-a"):
    # Exercise the shared transport on an independently retained route.
    value = await adapter.transport.request(
        "GET", f"/api/mcp/v1/courses/{segment(course)}/assessment-context", principal()
    )
    return value["grades"]


async def legacy_write(adapter):
    value = await adapter.transport.request(
        "POST",
        "/api/mcp/v1/courses/course-a/assignments",
        principal(),
        {"title": "Synthetic"},
    )
    return value["announcement"]


def test_read_uses_fixed_host_delegated_token_and_correlation_id():
    def handler(request):
        assert request.url.host == "sakai.example.test"
        assert request.url.path == "/api/mcp/v1/courses/course-a/assessment-context"
        assert request.headers["authorization"] == "Bearer synthetic-token"
        assert request.headers["x-correlation-id"]
        return httpx.Response(
            200, json={"grades": [{"id": "grade-a", "title": "Field Methods"}]}
        )

    rows = asyncio.run(legacy_read(client(handler)))
    assert rows == [{"id": "grade-a", "title": "Field Methods"}]


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
        asyncio.run(legacy_read(client(lambda _: httpx.Response(status))))
    assert error.value.code == code


def test_transient_read_is_retried_with_bounded_attempts():
    attempts = 0

    def handler(_):
        nonlocal attempts
        attempts += 1
        return httpx.Response(503 if attempts < 3 else 200, json={"grades": []})

    assert asyncio.run(legacy_read(client(handler))) == []
    assert attempts == 3


def test_create_succeeds_once_and_does_not_accept_destination_from_arguments():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        assert request.url.host == "sakai.example.test"
        assert request.method == "POST"
        assert request.url.path.endswith("/courses/course-a/assignments")
        return httpx.Response(
            201, json={"announcement": {"id": "new-1", "courseId": "course-a"}}
        )

    result = asyncio.run(legacy_write(client(handler)))
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
        asyncio.run(legacy_write(client(handler)))
    assert error.value.code == ErrorCode.AMBIGUOUS_WRITE_OUTCOME
    assert calls == 1


def test_preconnect_create_failure_is_dependency_unavailable_without_retry():
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        raise httpx.ConnectTimeout("synthetic timeout", request=request)

    with pytest.raises(SakaiError) as error:
        asyncio.run(legacy_write(client(handler)))
    assert error.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE
    assert calls == 1


def test_committed_create_with_lost_response_is_reconciled_by_read_without_replay():
    announcements = []
    post_calls = 0

    def handler(request):
        nonlocal post_calls
        if request.method == "POST":
            post_calls += 1
            announcements.append(
                {
                    "announcementId": "created-once",
                    "siteId": "course-a",
                    "channel": "main",
                    "title": "Synthetic check",
                    "body": "Synthetic body",
                    "createdOn": 1790000000123,
                }
            )
            raise httpx.ReadTimeout(
                "synthetic response lost after commit", request=request
            )
        assert request.method == "GET"
        assert request.url.path == "/api/mcp/v1/courses/course-a/assessment-context"
        return httpx.Response(200, json={"grades": announcements})

    adapter = client(handler)
    with pytest.raises(SakaiError) as error:
        asyncio.run(legacy_write(adapter))
    assert error.value.code == ErrorCode.AMBIGUOUS_WRITE_OUTCOME
    visible = asyncio.run(legacy_read(adapter))
    assert [row["announcementId"] for row in visible] == ["created-once"]
    assert post_calls == 1


def test_invalid_course_id_and_oversize_response_are_rejected():
    with pytest.raises(SakaiError) as error:
        asyncio.run(
            legacy_read(client(lambda _: httpx.Response(200, json={"grades": []})), "")
        )
    assert error.value.code == ErrorCode.VALIDATION_ERROR
    with pytest.raises(SakaiError) as error:
        asyncio.run(
            legacy_read(client(lambda _: httpx.Response(200, content=b"x" * 1_000_001)))
        )
    assert error.value.code == ErrorCode.INTERNAL_ERROR


@pytest.mark.parametrize(
    "failure", ["connect", "read", "rate-limit", "malformed", "oversize"]
)
def test_read_failures_are_bounded_and_recover_after_dependency_restoration(failure):
    attempts = 0
    healthy = False

    def handler(request):
        nonlocal attempts
        attempts += 1
        if healthy:
            return httpx.Response(200, json={"grades": [{"id": "grade-a"}]})
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
        asyncio.run(legacy_read(adapter))
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
    assert asyncio.run(legacy_read(adapter)) == [{"id": "grade-a"}]
    assert attempts == (4 if failure in ("connect", "read") else 2)


def test_declared_oversize_body_is_rejected_before_stream_consumption():
    def handler(_):
        return httpx.Response(
            200, headers={"content-length": "1000001"}, content=b"private body"
        )

    with pytest.raises(SakaiError) as error:
        asyncio.run(legacy_read(client(handler)))
    assert error.value.code == ErrorCode.INTERNAL_ERROR
