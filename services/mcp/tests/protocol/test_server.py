import asyncio

import httpx
import pytest
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.exceptions import ToolError

import sakai_mcp.server as server_module
from sakai_mcp.auth import EntraTokenVerifier
from sakai_mcp.sakai_client import ErrorCode, SakaiError
from sakai_mcp.server import create_server
from tests.helpers import settings


class FakeClient:
    writes = 0
    deny_privileged = False

    async def list_my_courses(self, _):
        return [{"id": "course-a", "title": "Field Methods"}]

    async def get_my_grades(self, _, course_id):
        assert course_id == "course-a"
        return [{"itemId": 10, "title": "Lab 1", "score": "18", "pointsPossible": 20.0}]

    async def get_course_announcements(self, _, course_id):
        assert course_id == "course-a"
        return [
            {"id": "one", "title": "Orientation", "body": "Welcome", "postedAt": 1_780_000_000_000},
            {"id": "two", "title": "Week 2", "body": "Read chapter 2", "postedAt": 1_780_000_100_000},
        ]

    async def get_course_submissions(self, _, course_id, assignment_id):
        if self.deny_privileged:
            raise SakaiError(ErrorCode.FORBIDDEN)
        assert course_id == "course-a" and assignment_id == "assignment-a"
        return [{"id": "submission-a", "submitterIds": ["student-a"], "submittedAt": 1_780_000_000.5}]

    async def create_course_announcement(self, _, course_id, title, body):
        if self.deny_privileged:
            raise SakaiError(ErrorCode.FORBIDDEN)
        self.writes += 1
        assert course_id == "course-a" and title == "Lab update" and body == "Bring notebooks."
        return {"id": "new", "courseId": course_id, "title": title, "postedAt": 1_780_000_000_000}


def make_server(client):
    config = settings()
    return create_server(config, client, EntraTokenVerifier(config, lambda _: None))


def authorized(monkeypatch):
    monkeypatch.setattr(
        server_module,
        "get_access_token",
        lambda: AccessToken(token="synthetic", client_id="test", scopes=["mcp.access"]),
    )


def test_catalog_has_exactly_five_v1_tools_and_correct_write_hint():
    tools = asyncio.run(make_server(FakeClient()).list_tools())
    names = {tool.name for tool in tools}
    assert names == {
        "list_my_courses",
        "get_my_grades",
        "get_course_announcements",
        "get_course_submissions",
        "create_course_announcement",
    }
    write = next(tool for tool in tools if tool.name == "create_course_announcement")
    assert write.annotations is not None and write.annotations.idempotent_hint is False
    assert write.annotations.read_only_hint is False


def test_read_tools_and_pagination(monkeypatch):
    authorized(monkeypatch)
    server = make_server(FakeClient())
    courses = asyncio.run(server.call_tool("list_my_courses", {}))
    assert courses.structured_content == {"courses": [{"id": "course-a", "title": "Field Methods"}]}
    grades = asyncio.run(server.call_tool("get_my_grades", {"course_id": "course-a"}))
    assert grades.structured_content["grades"][0]["score"] == "18"
    first = asyncio.run(server.call_tool("get_course_announcements", {"course_id": "course-a", "limit": 1}))
    assert first.structured_content["next_cursor"] == "1"
    assert first.structured_content["items"][0]["posted_at"].endswith("Z")
    second = asyncio.run(server.call_tool("get_course_announcements", {"course_id": "course-a", "cursor": "1"}))
    assert second.structured_content["next_cursor"] is None
    submissions = asyncio.run(server.call_tool("get_course_submissions", {"course_id": "course-a", "assignment_id": "assignment-a"}))
    assert submissions.structured_content["items"][0]["submitted_at"].endswith(".500000Z")


def test_missing_principal_and_manual_student_privileged_calls_fail(monkeypatch):
    monkeypatch.setattr(server_module, "get_access_token", lambda: None)
    server = make_server(FakeClient())
    with pytest.raises(ToolError, match="UNAUTHENTICATED"):
        asyncio.run(server.call_tool("list_my_courses", {}))
    authorized(monkeypatch)
    client = FakeClient()
    client.deny_privileged = True
    server = make_server(client)
    with pytest.raises(ToolError, match="FORBIDDEN"):
        asyncio.run(server.call_tool("get_course_submissions", {"course_id": "course-a", "assignment_id": "assignment-a"}))
    with pytest.raises(ToolError, match="FORBIDDEN"):
        asyncio.run(server.call_tool("create_course_announcement", {"course_id": "course-a", "title": "Lab update", "body": "Bring notebooks."}))
    assert client.writes == 0


def test_invalid_pagination_is_rejected(monkeypatch):
    authorized(monkeypatch)
    server = make_server(FakeClient())
    with pytest.raises(ToolError, match="VALIDATION_ERROR"):
        asyncio.run(server.call_tool("get_course_announcements", {"course_id": "course-a", "cursor": "-1"}))


def test_streamable_http_rejects_missing_bearer():
    server = make_server(FakeClient())
    app = server.streamable_http_app(stateless_http=True, json_response=True, host="mcp.example.test")

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.test") as client:
            return await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})

    response = asyncio.run(run())
    assert response.status_code == 401
    assert "Bearer" in response.headers["www-authenticate"]


def test_streamable_http_accepts_valid_bearer_and_lists_five_tools():
    class FakeVerifier:
        async def verify_token(self, token):
            if token != "valid":
                return None
            return AccessToken(token=token, client_id="test", scopes=["mcp.access"], resource=settings().mcp_audience)

    server = create_server(settings(), FakeClient(), FakeVerifier())
    app = server.streamable_http_app(stateless_http=True, json_response=True, host="mcp.example.test")

    async def run():
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="https://mcp.example.test") as client,
        ):
                headers = {
                    "Authorization": "Bearer valid",
                    "Accept": "application/json, text/event-stream",
                    "MCP-Protocol-Version": "2025-06-18",
                }
                initialize = await client.post(
                    "/mcp",
                    headers=headers,
                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}
                    }},
                )
                listed = await client.post(
                    "/mcp", headers=headers,
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                )
                called = await client.post(
                    "/mcp", headers=headers,
                    json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                        "name": "list_my_courses", "arguments": {}
                    }},
                )
                return initialize, listed, called

    initialize, listed, called = asyncio.run(run())
    assert initialize.status_code == 200
    assert listed.status_code == 200
    assert len(listed.json()["result"]["tools"]) == 5
    assert called.status_code == 200
    assert called.json()["result"]["structuredContent"]["courses"][0]["id"] == "course-a"
