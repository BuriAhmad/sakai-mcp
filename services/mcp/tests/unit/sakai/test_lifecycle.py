"""Preserve application lifespan state and release only service-owned HTTP clients."""

import asyncio
from contextlib import asynccontextmanager

import httpx
import pytest
from starlette.applications import Starlette

from sakai_mcp.bootstrap import manage_client_lifecycle
from sakai_mcp.sakai.client import SakaiClient
from tests.fixtures.authentication import settings
from tests.fixtures.sakai import FakeOBO


@pytest.mark.parametrize("failure", [None, "startup", "shutdown"])
def test_owned_http_closes_even_when_sdk_lifespan_fails(failure):
    async def run():
        events = []

        @asynccontextmanager
        async def sdk_lifespan(_):
            if failure == "startup":
                raise RuntimeError("startup")
            events.append("started")
            yield {"marker": "preserved"}
            events.append("stopped")
            if failure == "shutdown":
                raise RuntimeError("shutdown")

        app = Starlette(lifespan=sdk_lifespan)
        client = SakaiClient(settings(), FakeOBO())
        manage_client_lifecycle(app, client)

        async def enter():
            async with app.router.lifespan_context(app) as state:
                assert state == {"marker": "preserved"}
                assert not client.transport._http.is_closed

        if failure:
            with pytest.raises(RuntimeError, match=failure):
                await enter()
        else:
            await enter()
        assert client.transport._http.is_closed
        assert events == ([] if failure == "startup" else ["started", "stopped"])

    asyncio.run(run())


def test_injected_http_lifecycle_belongs_to_its_caller():
    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(200))
        ) as http:
            client = SakaiClient(settings(), FakeOBO(), http)
            app = Starlette()
            manage_client_lifecycle(app, client)
            async with app.router.lifespan_context(app):
                pass
            assert not http.is_closed
        assert http.is_closed

    asyncio.run(run())
