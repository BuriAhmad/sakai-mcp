import httpx

from sakai_mcp.contracts.assignment_setup import (
    CreateAssignmentRequest,
)
from sakai_mcp.sakai.client import SakaiClient
from tests.fixtures.authentication import settings
from tests.fixtures.sakai import FakeOBO


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
