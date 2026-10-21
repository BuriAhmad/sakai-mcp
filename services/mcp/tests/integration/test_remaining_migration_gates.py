"""Public SDK gate proofs with synthetic HTTP/storage; no servlet/auth acceptance."""

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import sakai_mcp.mcp.context as invocation
import sakai_mcp.workflows.grading as workflow
from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts.submissions import entry
from sakai_mcp.mcp.server import create_server
from sakai_mcp.security.auth import EntraTokenVerifier
from sakai_mcp.workflows.captures import assignment_revision
from tests.fixtures import grading_data as f
from tests.fixtures.five_tool_http import FiveToolHTTP
from tests.fixtures.sakai import principal


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
@pytest.mark.parametrize("case", ["valid", "denied"])
async def test_public_context_uses_existing_http_and_preserves_denial(
    monkeypatch, case
):
    from tests.fixtures.context_http import ContextHTTP

    wire = ContextHTTP()
    if case == "denied":
        wire.raw_status = 403
    client = wire.client()
    server = sdk(monkeypatch, client)
    arguments = {"course_id": f.COURSE, "assignment_id": f.ASSIGNMENT}
    if case == "valid":
        result = await server.call_tool("get_assignment_grading_context", arguments)
        assert result.structured_content["assignment"]["scale_factor"] == 100
        assert result.structured_content["supported"]["prepare"] is False
    else:
        with pytest.raises(ToolError, match="FORBIDDEN"):
            await server.call_tool("get_assignment_grading_context", arguments)
    assert all("/api/mcp/" not in r.url.path for r in wire.calls)
    assert len([r for r in wire.calls if "/annc/" in r.url.path]) == 1
