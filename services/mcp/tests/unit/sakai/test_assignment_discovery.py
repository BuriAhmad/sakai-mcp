"""Source-derived DTO fixtures through the real default operation facade."""

import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest

from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.client import SakaiClient
from tests.fixtures.authentication import settings
from tests.fixtures.sakai import FakeOBO, principal

ROW = json.loads(
    (Path(__file__).parents[2] / "fixtures/existing_http/wire.json").read_text()
)["assignment_discovery"]


def adapter(rows=None, permissions=None, status=200):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "GET" and "cookie" not in request.headers
        assert "/mcp/v1/" not in request.url.path
        path = request.url.path
        if path == "/direct/user/current.json":
            return httpx.Response(200, json={"id": "uid", "eid": "synthetic-eid"})
        if path == "/direct/site/course-a.json":
            return httpx.Response(
                200,
                json={
                    "id": "course-a",
                    "type": "course",
                    "pubView": False,
                    "published": True,
                },
            )
        if path.endswith("/userPerms.json"):
            return httpx.Response(
                200,
                json=permissions if permissions is not None else ["asn.grade"],
            )
        assert path == "/direct/assignment/site/course-a.json"
        return httpx.Response(
            status,
            json={
                "entityPrefix": "assignment",
                "assignment_collection": rows if rows is not None else [deepcopy(ROW)],
            },
        )

    return SakaiClient(
        settings(assignment_grading_enabled=True),
        FakeOBO(),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    ), calls


@pytest.mark.asyncio
async def test_default_discovery_is_grading_only_minimizes_fields_and_binds_cursor():
    second = {**ROW, "id": "assignment-b", "title": "Second"}
    client, calls = adapter([second, ROW, {**ROW, "id": "draft", "draft": True}])
    first = await client.grading.list_assignments(principal(), "course-a", None, 1)
    assert first.items[0].assignment_id == "assignment-a"
    assert first.items[0].configuration_revision.startswith("http1-")
    assert "PRIVATE" not in first.model_dump_json()
    next_page = await client.grading.list_assignments(
        principal(), "course-a", first.next_cursor, 1
    )
    assert (
        next_page.items[0].assignment_id == "assignment-b"
        and next_page.next_cursor is None
    )
    assert len(calls) == 8  # Fresh identity and authority on every page.
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("functions", [[], ["asn.submit"], ["asn.grade.groups"]])
async def test_group_only_or_non_grader_never_fetches_hydrated_site_action(functions):
    client, calls = adapter(permissions=functions)
    with pytest.raises(SakaiError) as error:
        await client.grading.list_assignments(principal(), "course-a", None, 50)
    assert error.value.code == ErrorCode.UNSUPPORTED_CAPABILITY
    assert len(calls) == 3


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rows",
    [
        [{**ROW, "context": "foreign"}],
        [ROW, ROW],
        [{k: v for k, v in ROW.items() if k != "draft"}],
    ],
)
async def test_invalid_relationship_duplicate_or_missing_flags_never_look_complete(
    rows,
):
    client, _ = adapter(rows)
    with pytest.raises(SakaiError):
        await client.grading.list_assignments(principal(), "course-a", None, 50)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code",
    [
        (403, ErrorCode.FORBIDDEN),
        (404, ErrorCode.NOT_FOUND),
        (500, ErrorCode.INTERNAL_ERROR),
        (503, ErrorCode.DEPENDENCY_UNAVAILABLE),
    ],
)
async def test_existing_failure_has_no_custom_fallback(status, code):
    client, _ = adapter(status=status)
    with pytest.raises(SakaiError) as error:
        await client.grading.list_assignments(principal(), "course-a", None, 50)
    assert error.value.code == code


@pytest.mark.asyncio
async def test_old_cursor_and_changed_observations_conflict_and_disabled_gate_sends_nothing():
    client, calls = adapter()
    with pytest.raises(SakaiError) as error:
        await client.grading.list_assignments(
            principal(), "course-a", "legacy-hash:0", 50
        )
    assert error.value.code == ErrorCode.CONFLICT
    disabled = SakaiClient(settings(), FakeOBO(), client.existing_transport._http)
    before = len(calls)
    with pytest.raises(SakaiError) as error:
        await disabled.grading.list_assignments(principal(), "course-a", None, 50)
    assert error.value.code == ErrorCode.UNSUPPORTED_CAPABILITY and len(calls) == before


@pytest.mark.asyncio
async def test_snapshot_change_and_permission_revocation_between_pages():
    rows = [deepcopy(ROW), {**ROW, "id": "assignment-b"}]
    permissions = ["asn.grade"]
    client, calls = adapter(rows, permissions)
    page = await client.grading.list_assignments(principal(), "course-a", None, 1)
    rows[0]["gradeScaleMaxPoints"] = "20.0"
    with pytest.raises(SakaiError) as error:
        await client.grading.list_assignments(
            principal(), "course-a", page.next_cursor, 1
        )
    assert error.value.code == ErrorCode.CONFLICT
    permissions.clear()
    before = len(calls)
    with pytest.raises(SakaiError) as error:
        await client.grading.list_assignments(
            principal(), "course-a", page.next_cursor, 1
        )
    assert error.value.code == ErrorCode.UNSUPPORTED_CAPABILITY
    assert len(calls) == before + 3


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["announcements", "discovery"])
async def test_native_eid_mismatch_blocks_both_default_capabilities(operation):
    from dataclasses import replace

    class MismatchedOBO(FakeOBO):
        async def acquire(self, token):
            return replace(await super().acquire(token), sakai_eid="foreign-eid")

    client, calls = adapter()
    client.existing_transport.obo = MismatchedOBO()
    with pytest.raises(SakaiError) as error:
        if operation == "announcements":
            await client.announcements.get_course_announcements(principal(), "course-a")
        else:
            await client.grading.list_assignments(principal(), "course-a", None, 50)
    assert error.value.code == ErrorCode.FORBIDDEN
    assert [r.url.path for r in calls] == ["/direct/user/current.json"]
