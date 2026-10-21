import asyncio

import pytest

from sakai_mcp.mcp.server import create_server
from sakai_mcp.security.auth import EntraTokenVerifier
from tests.fixtures.authentication import settings
from tests.fixtures.sakai import FakeClient, principal


@pytest.mark.parametrize(
    "setup,grading,count",
    [(False, False, 5), (True, False, 8), (False, True, 18), (True, True, 21)],
)
def test_independent_catalog_gates(setup, grading, count):
    config = settings(
        assignment_setup_enabled=setup, assignment_grading_enabled=grading
    )
    server = create_server(
        config, FakeClient(), EntraTokenVerifier(config, lambda _: None)
    )
    catalog = asyncio.run(server.list_tools())
    assert len(catalog) == count
    assert (
        {
            "get_assignment_grading_context",
            "list_assignment_submissions",
            "save_assignment_grades",
            "release_assignment_grades",
        }
        <= {t.name for t in catalog}
    ) == grading
    if grading:
        save = next(t for t in catalog if t.name == "save_assignment_grades")
        assert (
            save.annotations.read_only_hint is False
            and save.annotations.idempotent_hint is False
        )
        assert "expected_grade_revision" in str(save.input_schema)
        assert "invoke" not in save.input_schema["properties"]


def test_grading_tool_invocation_validates_and_forwards(monkeypatch):
    import sakai_mcp.mcp.context as tools

    monkeypatch.setattr(tools, "get_access_token", principal)

    class Client(FakeClient):
        async def list_assignment_submissions(self, token, request):
            assert request.limit == 50
            return {
                "items": [],
                "next_cursor": None,
                "snapshot_revision": "snapshot",
                "observed_at": "2026-10-09T00:00:00Z",
                "completeness": {"complete": True, "scope": "site", "reasons": []},
                "warnings": [],
            }

    config = settings(assignment_grading_enabled=True)
    server = create_server(config, Client(), EntraTokenVerifier(config, lambda _: None))
    result = asyncio.run(
        server.call_tool(
            "list_assignment_submissions",
            {"course_id": "course-a", "assignment_id": "assignment-a"},
        )
    )
    assert result.is_error is not True
