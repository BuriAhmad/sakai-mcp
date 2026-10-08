import asyncio
import json

import httpx
import pytest
from pydantic import ValidationError

from sakai_mcp.assessment_models import (
    CreateAssignmentRequest,
    PublishAssignmentRequest,
)
from sakai_mcp.assessment_validation import validate_create, validate_window
from sakai_mcp.sakai_client import ErrorCode, SakaiClient, SakaiError
from tests.helpers import settings
from tests.unit.test_sakai_client import FakeOBO, principal


def request(**changes):
    payload = {
        "course_id": "course-a",
        "title": "Assignment 3",
        "instructions": "Submit a report and source archive.",
        "timezone": "Asia/Karachi",
        "visible_at": None,
        "open_at": "2026-10-12T09:00:00+05:00",
        "due_at": "2026-10-26T09:00:00+05:00",
        "close_at": "2026-10-26T09:00:00+05:00",
        "max_points": 100.0,
        "submission_type": "attachments_only",
        "resubmission": {"count": 0, "until": None},
        "publication": "published",
        "attachment_resource_refs": [],
        "gradebook": {"mode": "none"},
        "calendar_deadline": "none",
    }
    payload.update(changes)
    return CreateAssignmentRequest.model_validate(payload)


def partial():
    return {
        "outcome": "partial",
        "course_id": "course-a",
        "assignment_id": "assignment-a",
        "assignment": None,
        "gradebook": {
            "gradebook_item_id": "21",
            "external_id": "/assignment/a/course-a/assignment-a",
            "category_id": "5",
            "mode": "new_external",
            "status": "linked",
            "released": False,
            "counted": False,
        },
        "calendar": {"event_id": None, "calendar_reference": None, "status": "missing"},
        "verified_at": None,
        "remaining_steps": ["link_calendar", "publish_assignment", "verify_setup"],
        "warnings": [],
        "failure": {
            "code": "PARTIAL_SUCCESS",
            "stage": "link_calendar",
            "reason": "Main Calendar unavailable",
            "retry_safe": False,
        },
    }


def adapter(handler, enabled=True):
    return SakaiClient(
        settings(assignment_setup_enabled=enabled),
        FakeOBO(),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


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
        asyncio.run(client.create_assignment(principal(), request(**changes)))
    if isinstance(error.value, SakaiError):
        assert error.value.code == ErrorCode.VALIDATION_ERROR
    assert not calls


def test_dst_gap_and_wrong_offset_rejected_but_explicit_overlap_offset_valid():
    with pytest.raises(ValueError):
        validate_create(
            request(
                timezone="America/New_York",
                open_at="2026-03-08T02:30:00-05:00",
                due_at="2026-03-09T09:00:00-04:00",
                close_at="2026-03-09T09:00:00-04:00",
            )
        )
    validate_create(
        request(
            timezone="America/New_York",
            open_at="2026-11-01T01:30:00-04:00",
            due_at="2026-11-02T09:00:00-05:00",
            close_at="2026-11-02T09:00:00-05:00",
        )
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"max_points": float("inf")},
        {"max_points": float("nan")},
        {"max_points": True},
        {"resubmission": {"count": True, "until": None}},
        {"gradebook": {"mode": "none", "category_id": "5"}},
    ],
)
def test_numeric_coercion_and_unsupported_fields_rejected(changes):
    with pytest.raises(ValidationError):
        request(**changes)


def test_window_requires_paired_bounded_offset_instants():
    validate_window(None, None)
    for start, end in [
        ("2026-10-01T00:00:00Z", None),
        (None, "2026-10-01T00:00:00Z"),
        ("2026-10-01T00:00:00Z", "2027-10-01T00:00:00Z"),
        ("2026-10-02T00:00:00Z", "2026-10-01T00:00:00Z"),
    ]:
        with pytest.raises(ValueError):
            validate_window(start, end)


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

    result = asyncio.run(adapter(handle).create_assignment(principal(), request()))
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
        asyncio.run(adapter(handle).create_assignment(principal(), request()))
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
        asyncio.run(adapter(handle).publish_assignment(principal(), r)).assignment_id
        == "assignment-a"
    )
    assert len(calls) == 1


def test_disabled_catalog_prevents_transport():
    calls = []
    with pytest.raises(SakaiError, match="UNSUPPORTED_CAPABILITY"):
        asyncio.run(
            adapter(lambda r: calls.append(r), False).create_assignment(
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
            adapter(handle).get_course_assessment_context(
                principal(),
                "course-a",
                "2026-10-01T00:00:00+05:00",
                "2026-10-30T00:00:00+05:00",
            )
        )
    assert len(calls) == 1


def test_new_capability_denial_does_not_change_v1_ambiguous_5xx_policy():
    with pytest.raises(SakaiError, match="UNSUPPORTED_CAPABILITY"):
        asyncio.run(adapter(lambda _: httpx.Response(501)).create_assignment(principal(), request()))
    with pytest.raises(SakaiError, match="AMBIGUOUS_WRITE_OUTCOME"):
        asyncio.run(adapter(lambda _: httpx.Response(501)).create_course_announcement(principal(), "course-a", "Title", "Body"))
