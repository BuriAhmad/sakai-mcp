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
from tests.fixtures.assignment_setup import request as setup_request
from tests.fixtures.authentication import KEY, TENANT, settings, token
from tests.fixtures.five_tool_http import FiveToolHTTP, gradebook_table
from tests.fixtures.grading_http import GradingHTTP
from tests.fixtures.setup_http import SetupHTTP

STUDENT = "00000000-0000-0000-0000-000000000001"
INSTRUCTOR = "00000000-0000-0000-0000-000000000002"


def test_composed_pipeline_keeps_users_and_write_permission_separate():
    config = settings(assignment_grading_enabled=True, assignment_setup_enabled=True)
    inbound = EntraTokenVerifier(config, lambda _: KEY.public_key())
    writes = []
    wires = {STUDENT: FiveToolHTTP(), INSTRUCTOR: GradingHTTP()}
    wires[INSTRUCTOR].native_uid = "uid-2"
    wires[STUDENT].functions = ["gradebook.viewOwnGrades"]
    wires[INSTRUCTOR].functions = list(
        dict.fromkeys(
            [
                *wires[INSTRUCTOR].functions,
                "gradebook.gradeAll",
                "gradebook.editAssignments",
                "section.role.instructor",
            ]
        )
    )
    wires[INSTRUCTOR].gradebook_data = gradebook_table()

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
                json=wires[downstream["oid"]].functions,
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
            assert request.url.path in {
                "/direct/assignment/setGrade.json",
                "/portal/tool/announcements-p",
                "/portal/tool/assignments-p",
            }
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
            assert not discovered.get("isError"), discovered
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
            grade_observation = await call(
                instructor,
                "get_assignment_grades",
                {
                    "course_id": "course-a",
                    "assignment_id": "assignment-a",
                    "rows": [
                        {"submission_id": "submission-a", "sakai_user_id": "student-a"}
                    ],
                },
            )
            assert not grade_observation.get("isError"), grade_observation
            selected_grade = grade_observation["structuredContent"]["rows"][0]
            assert selected_grade["flags"]["grade_released"] is False
            assert selected_grade["gradebook_state"] == "available"
            assert selected_grade["gradebook_score"] == "7.25"
            assert selected_grade["score"] is None
            assert not grade_observation["structuredContent"]["completeness"][
                "complete"
            ]
            # Exercise the capture/read/resource defaults through the actual SDK,
            # token verifier, OBO and existing native HTTP fixture.
            assignment = await call(
                instructor, "list_assignments", {"course_id": "course-a"}
            )
            export_id = "00000000-0000-0000-0000-000000000007"
            captured = await call(
                instructor,
                "export_assignment_submissions",
                {
                    "course_id": "course-a",
                    "assignment_id": "assignment-a",
                    "export_request_id": export_id,
                    "expected_assignment_revision": assignment["structuredContent"][
                        "items"
                    ][0]["configuration_revision"],
                    "submissions": [
                        {
                            "submission_id": "submission-a",
                            "expected_content_revision": detailed["structuredContent"][
                                "submission"
                            ]["content_revision"],
                        }
                    ],
                },
            )
            assert captured["structuredContent"]["status"] == "partial"
            exported = await call(
                instructor,
                "get_assignment_submission_export",
                {
                    "course_id": "course-a",
                    "assignment_id": "assignment-a",
                    "export_id": export_id,
                },
            )
            assert not exported.get("isError"), exported
            assert exported["structuredContent"]["completeness"]["complete"] is False
            artifact = exported["structuredContent"]["artifacts"][0]
            frozen = await call(
                instructor,
                "read_assignment_grading_resource",
                {"uri": artifact["resource"]["uri"]},
            )
            assert not frozen.get("isError"), frozen
            denied_export = await call(
                student,
                "get_assignment_submission_export",
                {
                    "course_id": "course-a",
                    "assignment_id": "assignment-a",
                    "export_id": export_id,
                },
            )
            assert denied_export["isError"] is True
            metadata = await call(
                instructor, "list_assignments", {"course_id": "course-a"}
            )
            approved_revision = metadata["structuredContent"]["items"][0][
                "configuration_revision"
            ]
            prepare_args = {
                "course_id": "course-a",
                "assignment_id": "assignment-a",
                "kind": "save",
                "operation_id": "00000000-0000-0000-0000-000000000001",
                "expected_assignment_revision": approved_revision,
                "grades": [
                    {
                        "submission_id": "submission-a",
                        "sakai_user_id": "student-a",
                        "expected_content_revision": detailed["structuredContent"][
                            "submission"
                        ]["content_revision"],
                        "expected_grade_revision": detailed["structuredContent"][
                            "submission"
                        ]["grade_revision"],
                        "score": "4",
                        "feedback": {"action": "preserve", "text": None},
                    }
                ],
            }
            prepared = await call(
                instructor, "prepare_assignment_grade_payload", prepare_args
            )
            assert not prepared.get("isError"), prepared
            assert prepared["structuredContent"]["validation"]["outcome"] == "validated"
            saved_grades = await call(
                instructor,
                "save_assignment_grades",
                prepared["structuredContent"]["commit_arguments"],
            )
            assert not saved_grades.get("isError"), saved_grades
            op_request = {
                "course_id": "course-a",
                "assignment_id": "assignment-a",
                "operation_id": prepare_args["operation_id"],
            }
            operation = await call(
                instructor, "get_assignment_grading_operation", op_request
            )
            assert not operation.get("isError"), operation
            assert operation["structuredContent"]["outcome"] == "partial"
            assert operation["structuredContent"]["rows"][0]["gradebook_score"] is None
            denied_operation = await call(
                student, "get_assignment_grading_operation", op_request
            )
            assert denied_operation["isError"] is True
            saved_detail = await call(
                instructor,
                "get_assignment_submission",
                {
                    "course_id": "course-a",
                    "assignment_id": "assignment-a",
                    "submission_id": "submission-a",
                },
            )
            prepare_args.update(
                kind="release", operation_id="00000000-0000-0000-0000-000000000002"
            )
            prepare_args["grades"] = [
                {
                    "submission_id": "submission-a",
                    "sakai_user_id": "student-a",
                    "expected_content_revision": saved_detail["structuredContent"][
                        "submission"
                    ]["content_revision"],
                    "expected_grade_revision": saved_detail["structuredContent"][
                        "submission"
                    ]["grade_revision"],
                    "expected_score": "4",
                    "expected_feedback_sha256": None,
                }
            ]
            returned_args = await call(
                instructor, "prepare_assignment_grade_payload", prepare_args
            )
            assert not returned_args.get("isError"), returned_args
            returned = await call(
                instructor,
                "release_assignment_grades",
                returned_args["structuredContent"]["commit_arguments"],
            )
            assert not returned.get("isError"), returned
            assert returned["structuredContent"]["rows"][0]["returned"] is True
            # Replace only the instructor's synthetic native view after the read
            # cohort; all three setup defaults still use the real SDK/JWT/OBO path.
            setup_wire = SetupHTTP()
            setup_wire.native_uid = "uid-2"
            wires[INSTRUCTOR] = setup_wire
            context = await call(
                instructor, "get_course_assessment_context", {"course_id": "course-a"}
            )
            assert not context.get("isError"), context
            assert context["structuredContent"]["complete"] is False
            setup = await call(
                instructor,
                "create_assignment",
                setup_request(publication="draft").model_dump(),
            )
            assert not setup.get("isError"), setup
            saved = setup["structuredContent"]
            assert (
                saved["outcome"] == "partial" and saved["assignment_id"] == "created-1"
            )
            observed_revision = next(
                w.removeprefix("configuration_revision: ")
                for w in saved["warnings"]
                if w.startswith("configuration_revision: ")
            )
            published = await call(
                instructor,
                "publish_assignment",
                {
                    "course_id": "course-a",
                    "assignment_id": saved["assignment_id"],
                    "expected_assignment_revision": observed_revision,
                    "gradebook": {"mode": "none"},
                    "calendar_deadline": "none",
                },
            )
            assert not published.get("isError"), published
            assert (
                published["structuredContent"]["outcome"] == "partial"
                and setup_wire.posts == 2
            )
            forbidden_setup = await call(
                student, "create_assignment", setup_request().model_dump()
            )
            assert forbidden_setup["isError"] is True and setup_wire.posts == 2
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
    assert writes == [INSTRUCTOR] * 5
