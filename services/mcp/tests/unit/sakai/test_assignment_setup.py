import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from sakai_mcp.contracts.assignment_setup import (
    PublishAssignmentRequest,
)
from sakai_mcp.errors import ErrorCode, SakaiError
from tests.fixtures.assignment_setup import adapter, partial, request
from tests.fixtures.sakai import principal


@pytest.mark.parametrize(
    "changes",
    [
        {"due_at": "2026-10-12T08:00:00+05:00"},
        {"close_at": "2026-10-25T09:00:00+05:00"},
        {"visible_at": "2026-10-13T09:00:00+05:00"},
        {"open_at": "2026-10-12T09:00:00"},
        {"timezone": "Not/AZone"},
        {"open_at": "2026-10-12T09:00:00+00:00"},
        {"resubmission": {"count": -1, "until": None}},
        {"resubmission": {"count": 0, "until": "2026-10-26T09:00:00+05:00"}},
        {"resubmission": {"count": 1, "until": "2026-10-25T09:00:00+05:00"}},
        {"publication": "draft", "calendar_deadline": "course_calendar"},
        {"attachment_resource_refs": ["/content/group/other-course/brief.pdf"]},
        {"title": " "},
    ],
)
def test_invalid_configuration_makes_zero_network_calls(changes):
    calls = []
    client = adapter(lambda r: calls.append(r))
    with pytest.raises((SakaiError, ValidationError)) as error:
        asyncio.run(
            client.assignments.create_assignment(principal(), request(**changes))
        )
    if isinstance(error.value, SakaiError):
        assert error.value.code == ErrorCode.VALIDATION_ERROR
    assert not calls


def test_partial_result_preserves_known_ids_and_nested_configuration():
    calls = []

    def handle(r):
        calls.append(r)
        data = json.loads(r.content)
        assert "course_id" not in data and data["resubmission"] == {
            "count": 0,
            "until": None,
        }
        assert r.url.host == "sakai.example.test" and r.url.path.endswith(
            "/course-a/assignments"
        )
        return httpx.Response(200, json=partial())

    result = asyncio.run(
        adapter(handle).assignments.create_assignment(principal(), request())
    )
    assert (
        result.assignment_id == "assignment-a"
        and result.gradebook.gradebook_item_id == "21"
    )
    assert result.outcome == "partial" and len(calls) == 1


@pytest.mark.parametrize(
    "failure",
    ["timeout", "server-error", "malformed", "wrong-course", "false-completion"],
)
def test_ambiguous_create_never_replays(failure):
    calls = []

    def handle(r):
        calls.append(r)
        if failure == "timeout":
            raise httpx.ReadTimeout("private detail", request=r)
        if failure == "server-error":
            return httpx.Response(503)
        if failure == "malformed":
            return httpx.Response(200, text="private content")
        data = partial()
        if failure == "wrong-course":
            data["course_id"] = "other-site"
        else:
            data["outcome"] = "complete"
        return httpx.Response(200, json=data)

    with pytest.raises(SakaiError) as error:
        asyncio.run(
            adapter(handle).assignments.create_assignment(principal(), request())
        )
    assert error.value.code == ErrorCode.AMBIGUOUS_WRITE_OUTCOME and len(calls) == 1
    assert "private" not in str(error.value)


def test_publish_reuses_known_assignment_path_without_create():
    calls = []

    def handle(r):
        calls.append(r)
        assert (
            r.url.path
            == "/api/mcp/v1/courses/course-a/assignments/assignment-a/publish"
        )
        assert json.loads(r.content)["expected_assignment_revision"] == "revision-a"
        return httpx.Response(200, json=partial())

    r = PublishAssignmentRequest(
        course_id="course-a",
        assignment_id="assignment-a",
        expected_assignment_revision="revision-a",
        gradebook={"mode": "none"},
        calendar_deadline="none",
    )
    assert (
        asyncio.run(
            adapter(handle).assignments.publish_assignment(principal(), r)
        ).assignment_id
        == "assignment-a"
    )
    assert len(calls) == 1


def test_disabled_catalog_prevents_transport():
    calls = []
    with pytest.raises(SakaiError, match="UNSUPPORTED_CAPABILITY"):
        asyncio.run(
            adapter(lambda r: calls.append(r), False).assignments.create_assignment(
                principal(), request()
            )
        )
    assert not calls


def test_context_query_is_encoded_and_does_not_initialize_tools():
    calls = []

    def handle(r):
        calls.append(r)
        assert r.method == "GET"
        assert r.url.params["window_start"] == "2026-10-01T00:00:00+05:00"
        return httpx.Response(403)

    with pytest.raises(SakaiError, match="FORBIDDEN"):
        asyncio.run(
            adapter(handle).assignments.get_course_assessment_context(
                principal(),
                "course-a",
                "2026-10-01T00:00:00+05:00",
                "2026-10-30T00:00:00+05:00",
            )
        )
    assert len(calls) == 1


def test_setup_denial_and_unconfigured_announcement_store_send_no_unjournaled_write():
    with pytest.raises(SakaiError, match="UNSUPPORTED_CAPABILITY"):
        asyncio.run(
            adapter(lambda _: httpx.Response(501)).assignments.create_assignment(
                principal(), request()
            )
        )
    with pytest.raises(SakaiError, match="DEPENDENCY_UNAVAILABLE"):
        asyncio.run(
            adapter(
                lambda _: httpx.Response(501)
            ).announcements.create_course_announcement(
                principal(), "course-a", "Title", "Body"
            )
        )
