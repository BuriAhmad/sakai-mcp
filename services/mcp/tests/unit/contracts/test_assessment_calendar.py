"""Ordinary native calendar events must not break instructor context reads."""

import pytest
from pydantic import ValidationError

from sakai_mcp.contracts.assignment_setup import AssessmentContext, CalendarEvent


def event(**changes):
    value = {
        "id": "event-a",
        "title": "Course meeting",
        "start_at": "2026-10-13T06:00:00Z",
        "end_at": "2026-10-13T07:00:00Z",
        "type": "Meeting",
        "assignment_id": "",
        "owner_tool_id": "",
    }
    value.update(changes)
    return value


@pytest.mark.parametrize("absent", ["", None])
def test_unset_native_calendar_fields_serialize_as_null(absent):
    value = CalendarEvent.model_validate(
        event(assignment_id=absent, owner_tool_id=absent)
    )
    assert value.model_dump()["assignment_id"] is None
    assert value.model_dump()["owner_tool_id"] is None


def test_owned_deadline_references_survive_unchanged():
    value = CalendarEvent.model_validate(
        event(assignment_id="assignment-a", owner_tool_id="sakai.assignment.grades")
    )
    assert value.assignment_id == "assignment-a"
    assert value.owner_tool_id == "sakai.assignment.grades"


@pytest.mark.parametrize(
    "changes", [{"id": ""}, {"assignment_id": "x" * 256}, {"owner_tool_id": 7}]
)
def test_invalid_references_are_still_rejected(changes):
    with pytest.raises(ValidationError):
        CalendarEvent.model_validate(event(**changes))


def test_frozen_context_contract_accepts_mixed_native_calendar_events():
    context = {
        "course": {
            "id": "course-a",
            "title": "Course A",
            "timezone": None,
            "timezone_source": "unknown",
        },
        "observed_at": "2026-10-13T05:00:00Z",
        "capabilities": {
            "create_site_assignment": True,
            "revise_assignment": True,
            "edit_gradebook_items": True,
            "read_calendar": True,
            "add_calendar_event": True,
            "create_announcement": True,
        },
        "complete": True,
        "sections": {
            name: {"status": "complete", "reason": None}
            for name in ("assignments", "gradebook", "calendar")
        },
        "assignments": [],
        "gradebook": {
            "available": True,
            "reason": None,
            "group_gradebooks_enabled": False,
            "category_mode": "none",
            "grade_entry_type": "points",
            "display_released_items": True,
            "course_grade_displayed": True,
            "categories": [],
            "items": [],
        },
        "calendar": {
            "scope": "site_main",
            "window_start": "2026-10-13T00:00:00Z",
            "window_end": "2026-10-15T00:00:00Z",
            "events": [
                event(),
                event(
                    id="event-b",
                    assignment_id="assignment-a",
                    owner_tool_id="sakai.assignment.grades",
                ),
            ],
        },
        "warnings": [],
    }
    result = AssessmentContext.model_validate(context)
    assert len(result.calendar.events) == 2
    assert result.calendar.events[0].assignment_id is None
    assert result.calendar.events[1].assignment_id == "assignment-a"
