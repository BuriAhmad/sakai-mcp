"""Public SDK gate proofs with synthetic HTTP/storage; no servlet/auth acceptance."""

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import sakai_mcp.mcp.context as invocation
from sakai_mcp.mcp.server import create_server
from sakai_mcp.security.auth import EntraTokenVerifier
from tests.fixtures import grading_data as f
from tests.fixtures.five_tool_http import FiveToolHTTP
from tests.fixtures.sakai import principal


def sdk(monkeypatch, client):
    monkeypatch.setattr(invocation, "get_access_token", principal)
    config = client.transport.settings
    return create_server(config, client, EntraTokenVerifier(config, lambda _: None))


@pytest.mark.asyncio
async def test_removed_mcq_tool_cannot_read_or_write(monkeypatch):
    wire = FiveToolHTTP()
    client = wire.client()
    server = sdk(monkeypatch, client)
    assert "prepare_assignment_mcq_grades" not in {
        t.name for t in await server.list_tools()
    }
    with pytest.raises(ToolError):
        await server.call_tool("prepare_assignment_mcq_grades", {})
    assert not wire.calls


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


@pytest.mark.asyncio
async def test_public_explicit_payload_save_return_and_readback(monkeypatch):
    from sakai_mcp.contracts.submissions import entry
    from sakai_mcp.grading.serialization import digest
    from sakai_mcp.workflows.captures import assignment_revision
    from tests.fixtures.grading_http import GradingHTTP

    wire = GradingHTTP()
    client = wire.client()
    server = sdk(monkeypatch, client)
    for kind, operation_id in [("save", f.EXPORT), ("release", f.PROPOSAL)]:
        _, assignment, rows = await client.submissions.source(
            principal(), f.COURSE, f.ASSIGNMENT
        )
        current = entry(rows[0], assignment)
        row = {
            "submission_id": current.submission_id,
            "sakai_user_id": current.student.sakai_user_id,
            "expected_content_revision": current.content_revision,
            "expected_grade_revision": current.grade_revision,
        }
        if kind == "save":
            row.update(score="4", feedback={"action": "preserve", "text": None})
        else:
            row.update(
                expected_score=current.score,
                expected_feedback_sha256=digest(rows[0].feedbackComment.encode())
                if rows[0].feedbackComment is not None
                else None,
            )
        prepared = await server.call_tool(
            "prepare_assignment_grade_payload",
            {
                "course_id": f.COURSE,
                "assignment_id": f.ASSIGNMENT,
                "kind": kind,
                "operation_id": operation_id,
                "expected_assignment_revision": assignment_revision(assignment),
                "grades": [row],
            },
        )
        assert len(wire.grade_posts) == (0 if kind == "save" else 1)
        assert prepared.structured_content["validation"]["outcome"] == "validated"
        saved = await server.call_tool(
            "save_assignment_grades" if kind == "save" else "release_assignment_grades",
            prepared.structured_content["commit_arguments"],
        )
        assert saved.structured_content["outcome"] == "partial"
        assert saved.structured_content["rows"][0]["stage"] == (
            "saved" if kind == "save" else "assignment_released"
        )
        receipt = await server.call_tool(
            "get_assignment_grading_operation",
            {
                "course_id": f.COURSE,
                "assignment_id": f.ASSIGNMENT,
                "operation_id": operation_id,
            },
        )
        assert receipt.structured_content["outcome"] == "partial"
    result = await server.call_tool(
        "get_assignment_grades",
        {
            "course_id": f.COURSE,
            "assignment_id": f.ASSIGNMENT,
            "rows": [{"submission_id": f.SUBMISSION, "sakai_user_id": "student-a"}],
        },
    )
    assert result.structured_content["rows"][0]["score"] == "4"
    assert result.structured_content["rows"][0]["flags"]["returned"] is True
    assert len(wire.grade_posts) == 2
    assert all("/api/mcp/" not in r.url.path for r in wire.calls)
