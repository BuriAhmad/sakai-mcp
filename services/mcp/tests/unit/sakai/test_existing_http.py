"""Existing-interface boundary tests; synthetic transport, no delegated live claim."""

import asyncio
from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.entitybroker import EntityBroker
from sakai_mcp.sakai.existing_transport import ExistingApiTransport
from sakai_mcp.sakai.operations import (
    CONTENT,
    CURRENT_USER,
    OPERATIONS,
    SET_GRADE,
    SOAP_ASSIGNMENTS,
    SOAP_CREATE_GET,
    USER_PERMISSIONS,
    Effect,
)
from sakai_mcp.sakai.webapi import WebApi
from tests.fixtures.authentication import settings
from tests.fixtures.sakai import FakeOBO, principal


@pytest.mark.asyncio
async def test_narrow_clients_extract_fields_and_do_not_inherit_credentials():
    import json

    fixtures = json.loads(
        (Path(__file__).parents[2] / "fixtures/existing_http/wire.json").read_text()
    )
    paths = []
    responses = {
        "/api/users/me/sites": fixtures["sites"],
        "/direct/user/current.json": fixtures["current_user"],
        "/direct/site/course-a.json": fixtures["site"],
        "/direct/site/course-a/userPerms.json": fixtures["user_permissions"],
    }

    def handler(request):
        paths.append(request.url.path)
        assert request.url.host == "sakai.example.test"
        assert request.method == "GET"
        assert not request.url.query
        assert request.headers["authorization"] == "Bearer synthetic-token"
        assert "cookie" not in request.headers
        assert "x-private" not in request.headers
        assert "x-mcp-flow" not in request.headers
        return httpx.Response(
            200,
            json=responses[request.url.path],
            headers={"set-cookie": "other=private"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        cookies={"JSESSIONID": "borrowed-browser"},
        headers={"X-Private": "do-not-send"},
        auth=("wrong", "password"),
    ) as http:
        transport = ExistingApiTransport(settings(), FakeOBO(), http)
        web, direct = WebApi(transport), EntityBroker(transport)
        assert len((await web.sites(principal())).sites) == 4
        user = await direct.current_user(principal())
        assert user.id == "synthetic-user-a" and user.eid == "synthetic-eid"
        assert "email" not in user.model_dump()
        assert (await direct.site(principal(), "course-a")).id == "course-a"
        assert await direct.user_permissions(principal(), "course-a") == frozenset(
            {"site.visit", "annc.read"}
        )
        await transport.aclose()
        assert not http.is_closed  # Injected lifecycle remains caller-owned.
    assert len(paths) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("op", [o for o in OPERATIONS.values() if o.blocked_reason])
async def test_unaccepted_operations_reject_before_obo_and_http(op):
    def unexpected(_):
        pytest.fail("Blocked operation reached HTTP")

    obo = FakeOBO()
    async with httpx.AsyncClient(transport=httpx.MockTransport(unexpected)) as http:
        transport = ExistingApiTransport(settings(), obo, http)
        with pytest.raises(SakaiError) as error:
            await transport.json(op, principal())
        assert error.value.code in {
            ErrorCode.UNSUPPORTED_CAPABILITY,
            ErrorCode.VALIDATION_ERROR,
        }
    assert obo.calls == 0


@pytest.mark.asyncio
async def test_copied_descriptor_cannot_bypass_review_gate():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: pytest.fail())
    ) as http:
        transport = ExistingApiTransport(settings(), FakeOBO(), http)
        with pytest.raises(SakaiError) as error:
            await transport.json(
                replace(CURRENT_USER, template="/api/login"), principal()
            )
        assert error.value.code == ErrorCode.VALIDATION_ERROR


def test_semantics_determine_retry_policy_not_http_verb():
    assert SOAP_CREATE_GET.method == "GET" and SOAP_CREATE_GET.attempts == 1
    assert SET_GRADE.attempts == 1
    assert SOAP_ASSIGNMENTS.method == "POST" and SOAP_ASSIGNMENTS.attempts == 3
    assert all(o.attempts == 1 for o in OPERATIONS.values() if o.effect != Effect.READ)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["connect", "read", "503"])
async def test_read_retries_are_bounded_and_same_operation_only(failure):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if failure == "connect":
            raise httpx.ConnectTimeout("private", request=request)
        if failure == "read":
            raise httpx.ReadTimeout("private", request=request)
        return httpx.Response(503, text="private")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SakaiError) as error:
            await ExistingApiTransport(settings(), FakeOBO(), http).json(
                CURRENT_USER, principal()
            )
    assert error.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE
    assert len(calls) == 3 and len(set(calls)) == 1
    assert "private" not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code",
    [
        (401, ErrorCode.UNAUTHENTICATED),
        (403, ErrorCode.FORBIDDEN),
        (404, ErrorCode.NOT_FOUND),
        (429, ErrorCode.RATE_LIMITED),
        (302, ErrorCode.INTERNAL_ERROR),
    ],
)
async def test_denials_and_redirects_never_fall_back_or_retry(status, code):
    calls = 0

    def handler(_):
        nonlocal calls
        calls += 1
        return httpx.Response(
            status, headers={"location": "https://foreign.example.test/private"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SakaiError) as error:
            await ExistingApiTransport(settings(), FakeOBO(), http).json(
                CURRENT_USER, principal()
            )
    assert error.value.code == code and calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body,headers",
    [
        (b'{"id":"a","id":"b"}', {}),
        (b'{"score":NaN}', {}),
        (b"null", {"content-type": "text/html"}),
        (b"{}", {"content-encoding": "gzip"}),
        (b"{}", {"content-length": "3"}),
        (b"{}", {"content-length": "1000001"}),
        (b"{}", {"content-length": "-1"}),
        (b"{}", {"content-length": "2, 2"}),
        (b"x" * 1000001, {}),
        ('{"id":"a"}'.encode("utf-16"), {}),
    ],
)
async def test_malformed_or_oversize_success_is_rejected(body, headers):
    calls = 0

    def handler(_):
        nonlocal calls
        calls += 1
        return httpx.Response(
            200, content=body, headers={"content-type": "application/json", **headers}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SakaiError):
            await ExistingApiTransport(settings(), FakeOBO(), http).json(
                CURRENT_USER, principal()
            )
    assert calls == 1


@pytest.mark.parametrize(
    "site", ["", "..", "a/b", "a%2fb", "a;b", " a", "a\\b", "a?b", "a#b", "a\nb", "a:b"]
)
def test_path_grammar_rejects_ambiguous_identifiers(site):
    with pytest.raises(SakaiError):
        USER_PERMISSIONS.path({"site": site})


@pytest.mark.parametrize(
    "resource",
    [
        None,
        "/content/url/foreign",
        "/content/group/a/../b",
        "/content/attachment/a/%2f",
        "https://foreign.example.test",
        "/content/group/a//b",
    ],
)
def test_content_path_requires_canonical_native_reference(resource):
    with pytest.raises(SakaiError):
        CONTENT.path({"resource": resource})


def test_path_encoding_and_query_allowlist():
    assert (
        CONTENT.path({"resource": "/content/group/course-a/Lab notes.txt"})
        == "/access/content/group/course-a/Lab%20notes.txt"
    )
    for parameters, query in [
        ({"site": "a", "extra": "b"}, {}),
        ({"site": "a"}, {"sessionid": "borrowed"}),
    ]:
        with pytest.raises(SakaiError):
            USER_PERMISSIONS.path(parameters, query)


@pytest.mark.asyncio
async def test_site_relationship_mismatch_fails_closed():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(
                200, json={"id": "other-site", "type": "course", "published": True}
            )
        )
    ) as http:
        with pytest.raises(SakaiError) as error:
            await EntityBroker(ExistingApiTransport(settings(), FakeOBO(), http)).site(
                principal(), "course-a"
            )
    assert error.value.code == ErrorCode.CONFLICT


@pytest.mark.asyncio
async def test_owned_client_closes_and_cancel_is_not_retried():
    transport = ExistingApiTransport(settings(), FakeOBO())
    await transport.aclose()
    assert transport._http.is_closed
    calls = 0

    def cancelled(_):
        nonlocal calls
        calls += 1
        raise asyncio.CancelledError

    async with httpx.AsyncClient(transport=httpx.MockTransport(cancelled)) as http:
        with pytest.raises(asyncio.CancelledError):
            await ExistingApiTransport(settings(), FakeOBO(), http).json(
                CURRENT_USER, principal()
            )
    assert calls == 1
