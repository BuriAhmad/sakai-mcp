"""Compose protocol, JWT, OBO, and Sakai HTTP adapters without live credentials."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import jwt

from sakai_mcp.mcp.server import create_server
from sakai_mcp.sakai.client import SakaiClient
from sakai_mcp.security.auth import EntraTokenVerifier
from sakai_mcp.security.obo import OBOProvider
from sakai_mcp.storage.memory import MemoryObjectStore
from sakai_mcp.storage.records import PrivateRecords
from tests.fixtures.authentication import KEY, TENANT, settings, token
from tests.fixtures.five_tool_http import FiveToolHTTP

STUDENT = "00000000-0000-0000-0000-000000000001"
INSTRUCTOR = "00000000-0000-0000-0000-000000000002"


def test_composed_pipeline_keeps_users_and_write_permission_separate():
    config = settings(assignment_grading_enabled=True)
    inbound = EntraTokenVerifier(config, lambda _: KEY.public_key())
    writes = []
    wires = {STUDENT: FiveToolHTTP(), INSTRUCTOR: FiveToolHTTP()}
    wires[STUDENT].functions = ["gradebook.viewOwnGrades"]

    def exchange(assertion, scopes):
        upstream = jwt.decode(
            assertion,
            KEY.public_key(),
            algorithms=["RS256"],
            audience=config.mcp_audience,
        )
        assert scopes == [f"{config.sakai_audience}/sakai.mcp.access"]
        now = datetime.now(UTC)
        downstream = jwt.encode(
            {
                "iss": str(config.sakai_issuer),
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
        downstream = jwt.decode(
            bearer,
            KEY.public_key(),
            algorithms=["RS256"],
            audience=config.sakai_audience,
        )
        assert request.url.host == "sakai.example.test"
        assert request.headers["x-correlation-id"]
        course = "course-a" if downstream["oid"] == STUDENT else "course-b"
        if request.url.path == "/api/mcp/v1/courses":
            raise AssertionError("Retired course endpoint called")
        if request.url.path == "/direct/user/current.json":
            return httpx.Response(
                200,
                json={
                    "id": "uid-" + downstream["oid"][-1],
                    "eid": "synthetic-" + downstream["oid"][-1],
                },
            )
        if request.url.path == "/api/users/me/sites":
            return httpx.Response(
                200,
                json={
                    "sites": [
                        {
                            "siteId": course,
                            "title": "Synthetic Field Methods",
                            "course": True,
                        }
                    ]
                },
            )
        if request.url.path == "/direct/site/" + course + ".json":
            return httpx.Response(
                200,
                json={
                    "id": course,
                    "type": "course",
                    "published": True,
                    "pubView": False,
                },
            )
        if request.url.path == "/direct/announcement/site/" + course + ".json":
            return httpx.Response(
                200,
                json=[
                    {
                        "announcementId": "message-" + course,
                        "siteId": course,
                        "channel": "main",
                        "title": "Synthetic",
                        "body": "<p>Untrusted</p>",
                        "createdOn": 1790000000123,
                    }
                ],
            )
        if request.url.path == "/direct/site/" + course + "/userPerms.json":
            return httpx.Response(
                200,
                json=["asn.grade", "annc.new", "gradebook.viewOwnGrades"]
                if downstream["oid"] == INSTRUCTOR
                else ["gradebook.viewOwnGrades"],
            )
        if request.url.path == "/direct/assignment/site/" + course + ".json":
            assert downstream["oid"] == INSTRUCTOR
            row = json.loads(
                (
                    Path(__file__).parents[1] / "fixtures/existing_http/wire.json"
                ).read_text()
            )["assignment_discovery"]

            return httpx.Response(200, json=[{**row, "context": course}])
        wire = wires[downstream["oid"]]
        wire.expected_token = bearer
        wire.native_eid = "synthetic-" + downstream["oid"][-1]
        if request.method == "POST":
            assert request.url.path == "/portal/tool/announcements-p"
            writes.append(downstream["oid"])
        return wire(request)

    obo = OBOProvider(
        config,
        inbound,
        exchange=exchange,
        downstream_signing_key=lambda _: KEY.public_key(),
    )
    client = SakaiClient(
        config,
        obo,
        httpx.AsyncClient(transport=httpx.MockTransport(sakai)),
        private_records=PrivateRecords(MemoryObjectStore()),
    )
    server = create_server(config, client, inbound)
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, host="mcp.example.test"
    )

    async def run():
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="https://mcp.example.test"
            ) as http,
        ):

            async def call(user_token, name, arguments):
                response = await http.post(
                    "/mcp",
                    headers={
                        "Authorization": "Bearer " + user_token,
                        "Accept": "application/json, text/event-stream",
                        "MCP-Protocol-Version": "2025-06-18",
                    },
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": name, "arguments": arguments},
                    },
                )
                assert response.status_code == 200
                return response.json()["result"]

            student = token(oid=STUDENT)
            instructor = token(oid=INSTRUCTOR)
            student_courses = await call(student, "list_my_courses", {})
            instructor_courses = await call(instructor, "list_my_courses", {})
            for user_token, course in [(student, "course-a"), (instructor, "course-b")]:
                news = await call(
                    user_token, "get_course_announcements", {"course_id": course}
                )
                assert (
                    news["structuredContent"]["items"][0]["id"] == "message-" + course
                )
                assert news["structuredContent"]["coverage"]["complete"] is False
            discovered = await call(
                instructor, "list_assignments", {"course_id": "course-b"}
            )
            assert (
                discovered["structuredContent"]["items"][0]["assignment_id"]
                == "assignment-a"
            )
            restricted = await call(
                student, "list_assignments", {"course_id": "course-a"}
            )
            assert restricted["isError"] is True
            own = await call(student, "get_my_grades", {"course_id": "course-a"})
            assert own["structuredContent"]["grades"][0]["itemId"] == 7
            submitted = await call(
                instructor,
                "get_course_submissions",
                {"course_id": "course-a", "assignment_id": "assignment-a"},
            )
            assert submitted["structuredContent"]["items"][0]["id"] == "submission-a"
            listed = await call(
                instructor,
                "list_assignment_submissions",
                {"course_id": "course-a", "assignment_id": "assignment-a"},
            )
            assert listed["structuredContent"]["completeness"]["complete"] is False
            detailed = await call(
                instructor,
                "get_assignment_submission",
                {
                    "course_id": "course-a",
                    "assignment_id": "assignment-a",
                    "submission_id": "submission-a",
                },
            )
            assert detailed["structuredContent"]["submission"]["flags"] is None
            resource = detailed["structuredContent"]["submission"]["inline_resource"][
                "uri"
            ]
            content = await call(
                instructor, "read_assignment_grading_resource", {"uri": resource}
            )
            assert not content.get("isError")
            denied = await call(
                student,
                "create_course_announcement",
                {
                    "course_id": "course-a",
                    "title": "Lab update",
                    "body": "Bring notebooks.",
                },
            )
            created = await call(
                instructor,
                "create_course_announcement",
                {
                    "course_id": "course-a",
                    "title": "Lab update",
                    "body": "Bring notebooks.",
                },
            )
            return student_courses, instructor_courses, denied, created

    student_courses, instructor_courses, denied, created = asyncio.run(run())
    assert student_courses["structuredContent"]["courses"][0]["id"] == "course-a"
    assert instructor_courses["structuredContent"]["courses"][0]["id"] == "course-b"
    assert denied["isError"] is True and "FORBIDDEN" in str(denied["content"])
    assert created["structuredContent"]["announcement"]["id"] == "created-once"
    assert writes == [INSTRUCTOR]
