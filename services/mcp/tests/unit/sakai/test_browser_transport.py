"""Synthetic native conversations prove transport lifecycle, not tool acceptance."""

from urllib.parse import parse_qs

import httpx
import pytest

from sakai_mcp.contracts.native_forms import NativeForm
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.browser_transport import BrowserTransport
from tests.fixtures.authentication import settings
from tests.fixtures.sakai import FakeOBO, principal

BASE = "https://sakai.example.test/portal/tool/placement-a"
FORM = NativeForm(
    BASE,
    (("sakai_csrf_token", "synthetic-csrf"), ("option", "")),
    frozenset({"sakai_csrf_token", "option"}),
    "synthetic-csrf",
)


@pytest.mark.asyncio
async def test_flow_uses_private_nonce_without_inheriting_credentials_and_closes_on_existing_read():
    requests = []

    def handler(request):
        requests.append(request)
        assert "cookie" not in request.headers
        assert "private-default" not in request.headers
        assert request.headers["authorization"] == "Bearer synthetic-token"
        if request.headers.get("x-mcp-flow-end"):
            assert (
                request.url.path == "/direct/user/current.json"
                and request.method == "GET"
            )
            return httpx.Response(200, json={"id": "synthetic-user"})
        if request.method == "POST":
            assert parse_qs(request.content.decode())["option"] == ["post"]
            return httpx.Response(
                302,
                headers={
                    "location": BASE + "?view=posted",
                    "set-cookie": "JSESSIONID=do-not-reuse",
                },
            )
        return httpx.Response(
            200, text="<html>synthetic</html>", headers={"content-type": "text/html"}
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        cookies={"browser": "private"},
        headers={"private-default": "private"},
        auth=("wrong", "password"),
    ) as http:
        transport = BrowserTransport(settings(), FakeOBO(), http)
        async with transport.conversation(principal(), "placement-a") as flow:
            page = await flow.navigate()
            assert page.data == b"<html>synthetic</html>"
            posted = await flow.submit(FORM, {"option": "post"}, academic=True)
            assert posted.url.endswith("?view=posted")
            assert "synthetic</html>" not in repr(posted)
        await transport.aclose()
        assert not http.is_closed
    assert [r.method for r in requests] == ["GET", "POST", "GET", "GET"]
    nonces = {r.headers["x-mcp-flow"] for r in requests}
    assert len(nonces) == 1 and len(nonces.pop()) == 64


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "500", "foreign", "307", "wrong-media"])
async def test_uncertain_academic_posts_are_never_replayed(failure):
    posts = 0

    def handler(request):
        nonlocal posts
        if request.headers.get("x-mcp-flow-end"):
            return httpx.Response(200)
        if request.method == "POST":
            posts += 1
            if failure == "timeout":
                raise httpx.ReadTimeout("private", request=request)
            if failure == "500":
                return httpx.Response(500)
            if failure == "foreign":
                return httpx.Response(
                    302, headers={"location": "https://foreign.example.test/private"}
                )
            if failure == "307":
                return httpx.Response(307, headers={"location": BASE})
            return httpx.Response(
                200, content=b"private bytes", headers={"content-type": "image/png"}
            )
        pytest.fail("A mutation was followed or replayed unexpectedly")

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http,
        BrowserTransport(settings(), FakeOBO(), http).conversation(
            principal(), "placement-a"
        ) as flow,
    ):
        with pytest.raises(SakaiError) as error:
            await flow.submit(FORM, {"option": "post"}, academic=True)
        assert error.value.code == ErrorCode.AMBIGUOUS_WRITE_OUTCOME
        assert "private" not in str(error.value)
    assert posts == 1


@pytest.mark.asyncio
async def test_post_redirect_then_read_failure_keeps_the_write_unknown():
    posts = 0

    def handler(request):
        nonlocal posts
        if request.headers.get("x-mcp-flow-end"):
            return httpx.Response(200)
        if request.method == "POST":
            posts += 1
            return httpx.Response(302, headers={"location": BASE})
        raise httpx.ConnectTimeout("private", request=request)

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http,
        BrowserTransport(settings(), FakeOBO(), http).conversation(
            principal(), "placement-a"
        ) as flow,
    ):
        with pytest.raises(SakaiError) as error:
            await flow.submit(FORM, {"option": "post"}, academic=True)
    assert error.value.code == ErrorCode.AMBIGUOUS_WRITE_OUTCOME and posts == 1


@pytest.mark.asyncio
async def test_preconnect_failure_and_navigation_are_single_attempts():
    calls = []

    def handler(request):
        calls.append(request)
        if request.headers.get("x-mcp-flow-end"):
            return httpx.Response(410)
        raise httpx.ConnectTimeout("private", request=request)

    async with (
        httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http,
        BrowserTransport(settings(), FakeOBO(), http).conversation(
            principal(), "placement-a"
        ) as flow,
    ):
        with pytest.raises(SakaiError) as error:
            await flow.navigate()
        assert error.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE
    assert len(calls) == 2 and calls[-1].headers.get("x-mcp-flow-end") == "1"


@pytest.mark.asyncio
async def test_closed_or_invalid_flow_never_sends_another_request():
    requests = []
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: (
                requests.append(r)
                or httpx.Response(200, text="ok", headers={"content-type": "text/html"})
            )
        )
    ) as http:
        transport = BrowserTransport(settings(), FakeOBO(), http)
        async with transport.conversation(principal(), "placement-a") as flow:
            with pytest.raises(SakaiError):
                await flow.navigate("https://foreign.example.test/private")
        assert not requests
        with pytest.raises(SakaiError) as error:
            await flow.navigate()
        assert error.value.code == ErrorCode.CONFLICT and not requests


@pytest.mark.asyncio
async def test_cleanup_failure_is_recorded_without_reauthentication_or_replay():
    calls = []

    def handler(request):
        calls.append(request)
        if request.headers.get("x-mcp-flow-end"):
            return httpx.Response(401)
        return httpx.Response(200, text="ok", headers={"content-type": "text/html"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        async with BrowserTransport(settings(), FakeOBO(), http).conversation(
            principal(), "placement-a"
        ) as flow:
            await flow.navigate()
        assert flow._state.cleanup_failed
        await flow.aclose()
    assert len(calls) == 2
