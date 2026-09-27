import asyncio

import httpx
from starlette.applications import Starlette

from sakai_mcp.asgi import add_health_routes


def test_liveness_and_readiness_are_local_and_unauthenticated():
    app = add_health_routes(Starlette())

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.test") as client:
            live = await client.get("/live")
            ready = await client.get("/ready")
            return live, ready

    live, ready = asyncio.run(check())
    assert live.status_code == 200 and live.json() == {"status": "live"}
    assert ready.status_code == 200 and ready.json() == {"status": "ready"}
