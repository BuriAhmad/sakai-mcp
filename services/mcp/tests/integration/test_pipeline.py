"""Compose protocol, JWT, OBO, and Sakai HTTP adapters without live credentials."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import jwt

from sakai_mcp.auth import EntraTokenVerifier
from sakai_mcp.obo import OBOProvider
from sakai_mcp.sakai_client import SakaiClient
from sakai_mcp.server import create_server
from tests.helpers import KEY, TENANT, settings, token

STUDENT = "00000000-0000-0000-0000-000000000001"
INSTRUCTOR = "00000000-0000-0000-0000-000000000002"


def test_composed_pipeline_keeps_users_and_write_permission_separate():
    config = settings()
    inbound = EntraTokenVerifier(config, lambda _: KEY.public_key())
    writes = []

    def exchange(assertion, scopes):
        upstream = jwt.decode(assertion, KEY.public_key(), algorithms=["RS256"], audience=config.mcp_audience)
        assert scopes == [f"{config.sakai_audience}/sakai.mcp.access"]
        now = datetime.now(UTC)
        downstream = jwt.encode(
            {
                "iss": str(config.mcp_issuer),
                "tid": str(TENANT),
                "oid": upstream["oid"],
                "aud": config.sakai_audience,
                "scp": "sakai.mcp.access",
                "extn.SakaiEid": ["synthetic-" + upstream["oid"][-1]],
                "exp": now + timedelta(minutes=20),
                "nbf": now - timedelta(minutes=1),
            },
            KEY,
            algorithm="RS256",
        )
        return {"access_token": downstream}

    def sakai(request):
        bearer = request.headers["authorization"].removeprefix("Bearer ")
        downstream = jwt.decode(bearer, KEY.public_key(), algorithms=["RS256"], audience=config.sakai_audience)
        assert request.url.host == "sakai.example.test"
        assert request.headers["x-correlation-id"]
        if request.url.path == "/api/mcp/v1/courses":
            course = "course-a" if downstream["oid"] == STUDENT else "course-b"
            return httpx.Response(200, json={"courses": [{"id": course, "title": "Synthetic Field Methods"}]})
        if request.method == "POST" and request.url.path.endswith("/announcements"):
            if downstream["oid"] == STUDENT:
                return httpx.Response(403)
            writes.append(downstream["oid"])
            return httpx.Response(201, json={"announcement": {"id": "new-1", "courseId": "course-b"}})
        return httpx.Response(404)

    obo = OBOProvider(config, inbound, exchange=exchange, downstream_signing_key=lambda _: KEY.public_key())
    client = SakaiClient(config, obo, httpx.AsyncClient(transport=httpx.MockTransport(sakai)))
    server = create_server(config, client, inbound)
    app = server.streamable_http_app(stateless_http=True, json_response=True, host="mcp.example.test")

    async def run():
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.test") as http,
        ):
            async def call(user_token, name, arguments):
                response = await http.post(
                    "/mcp",
                    headers={"Authorization": "Bearer " + user_token, "Accept": "application/json, text/event-stream",
                             "MCP-Protocol-Version": "2025-06-18"},
                    json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": arguments}},
                )
                assert response.status_code == 200
                return response.json()["result"]

            student = token(oid=STUDENT)
            instructor = token(oid=INSTRUCTOR)
            student_courses = await call(student, "list_my_courses", {})
            instructor_courses = await call(instructor, "list_my_courses", {})
            denied = await call(student, "create_course_announcement", {
                "course_id": "course-a", "title": "Lab update", "body": "Bring notebooks."
            })
            created = await call(instructor, "create_course_announcement", {
                "course_id": "course-b", "title": "Lab update", "body": "Bring notebooks."
            })
            return student_courses, instructor_courses, denied, created

    student_courses, instructor_courses, denied, created = asyncio.run(run())
    assert student_courses["structuredContent"]["courses"][0]["id"] == "course-a"
    assert instructor_courses["structuredContent"]["courses"][0]["id"] == "course-b"
    assert denied["isError"] is True and "FORBIDDEN" in str(denied["content"])
    assert created["structuredContent"]["announcement"]["id"] == "new-1"
    assert writes == [INSTRUCTOR]
