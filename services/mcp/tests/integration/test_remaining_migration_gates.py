"""Public SDK gate proofs with synthetic HTTP/storage; no servlet/auth acceptance."""

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

import sakai_mcp.mcp.context as invocation
import sakai_mcp.workflows.grading as workflow
from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts.submissions import entry
from sakai_mcp.mcp.server import create_server
from sakai_mcp.sakai.client import SakaiClient
from sakai_mcp.security.auth import EntraTokenVerifier
from sakai_mcp.workflows.captures import assignment_revision
from tests.fixtures import grading_data as f
from tests.fixtures.authentication import settings
from tests.fixtures.five_tool_http import FiveToolHTTP
from tests.fixtures.sakai import FakeOBO, principal


def sdk(monkeypatch, client):
    monkeypatch.setattr(invocation, "get_access_token", principal)
    config = client.transport.settings
    return create_server(config, client, EntraTokenVerifier(config, lambda _: None))


@pytest.mark.asyncio
async def test_public_mcq_partial_capture_stops_before_context_evaluator_and_storage(
    monkeypatch,
):
    wire = FiveToolHTTP()
    client = wire.client()
    _, assignment, rows = await client.submissions.source(
        principal(), f.COURSE, f.ASSIGNMENT
    )
    capture = await client.grading.export_assignment_submissions(
        principal(),
        native.ExportAssignmentSubmissionsRequest(
            course_id=f.COURSE,
            assignment_id=f.ASSIGNMENT,
            export_request_id=f.EXPORT,
            expected_assignment_revision=assignment_revision(assignment),
            submissions=[
                native.ExportSelection(
                    submission_id=row.id,
                    expected_content_revision=entry(row, assignment).content_revision,
                )
                for row in rows
            ],
        ),
    )
    assert capture.status == "partial"

    def forbidden(*args, **kwargs):
        pytest.fail("Incomplete capture reached a downstream grading stage")

    monkeypatch.setattr(client.grading, "get_assignment_grading_context", forbidden)
    monkeypatch.setattr(client.grading, "create_proposal", forbidden)
    monkeypatch.setattr(workflow, "evaluate_mcq", forbidden)
    store = client.grading.captures.store().store
    before = dict(store._objects)
    wire.calls.clear()
    with pytest.raises(ToolError, match="CONFLICT"):
        await sdk(monkeypatch, client).call_tool(
            "prepare_assignment_mcq_grades",
            {
                "course_id": f.COURSE,
                "assignment_id": f.ASSIGNMENT,
                "export_id": f.EXPORT,
                "proposal_id": f.PROPOSAL,
                "config": f.config().model_dump(),
            },
        )
    assert store._objects == before
    assert wire.calls
    assert all(
        request.method == "GET" and "/api/mcp/" not in request.url.path
        for request in wire.calls
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", ["valid", "denied", "scale_factor", "native_release_grades"]
)
async def test_public_context_retains_native_dependency_and_rejects_missing_state(
    monkeypatch, case
):
    value = f.context().model_dump()
    if case in {"scale_factor", "native_release_grades"}:
        value["assignment"].pop(case)
    calls = []

    def handler(request):
        calls.append(request)
        return (
            httpx.Response(403) if case == "denied" else httpx.Response(200, json=value)
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = SakaiClient(settings(assignment_grading_enabled=True), FakeOBO(), http)
        server = sdk(monkeypatch, client)
        arguments = {"course_id": f.COURSE, "assignment_id": f.ASSIGNMENT}
        if case == "valid":
            result = await server.call_tool("get_assignment_grading_context", arguments)
            assert result.structured_content["supported"]["prepare"] is False
            assert result.structured_content["supported"]["save"] is False
            assert result.structured_content["supported"]["release"] is False
        else:
            expected = "FORBIDDEN" if case == "denied" else "INTERNAL_ERROR"
            with pytest.raises(ToolError, match=expected):
                await server.call_tool("get_assignment_grading_context", arguments)
    assert len(calls) == 1
    assert calls[0].method == "GET"
    assert calls[0].url.path == (
        "/api/mcp/v1/courses/course-a/assignments/assignment-a/grading-context"
    )
