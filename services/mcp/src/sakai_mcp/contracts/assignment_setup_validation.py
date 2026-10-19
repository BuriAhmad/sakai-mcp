"""Cross-field validation before any assignment setup transport."""

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sakai_mcp.contracts.assignment_setup import CreateAssignmentRequest


def instant(value: str) -> datetime:
    if not re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?(?:Z|[+-]\d\d:\d\d)", value
    ):
        raise ValueError("Expected RFC3339 instant")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or value.endswith("-00:00") or result.microsecond % 1000:
        raise ValueError("Explicit known offset required")
    return result


def validate_window(start: str | None, end: str | None) -> None:
    if (start is None) != (end is None):
        raise ValueError("Both calendar bounds required")
    if start is not None and end is not None:
        first, last = instant(start), instant(end)
        if not first < last or last - first > timedelta(days=90):
            raise ValueError("Invalid calendar window")


def validate_create(request: CreateAssignmentRequest) -> None:
    try:
        zone = ZoneInfo(request.timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Unknown IANA timezone") from None
    values = [request.open_at, request.due_at, request.close_at]
    if request.visible_at is not None:
        values.append(request.visible_at)
    if request.resubmission.until is not None:
        values.append(request.resubmission.until)
    for value in values:
        stamp = instant(value)
        if stamp.utcoffset() != stamp.astimezone(zone).utcoffset():
            raise ValueError("Timezone and offset disagree")
    opened, due, closed = map(
        instant, [request.open_at, request.due_at, request.close_at]
    )
    if not opened < due <= closed:
        raise ValueError("Invalid assignment dates")
    if request.visible_at and instant(request.visible_at) > opened:
        raise ValueError("Visibility must not follow opening")
    resubmit = request.resubmission
    if resubmit.count == 0:
        if resubmit.until is not None:
            raise ValueError("Disabled resubmission has no deadline")
    elif resubmit.until is None or instant(resubmit.until) < closed:
        raise ValueError("Resubmission deadline must be at least close")
    if not request.title.strip() or not request.instructions.strip():
        raise ValueError("Blank assignment content")
    for ref in request.attachment_resource_refs:
        if not ref.startswith(
            f"/content/group/{request.course_id}/"
        ) or ".." in ref.split("/"):
            raise ValueError("Only same-course existing resources allowed")
    if len(set(request.attachment_resource_refs)) != len(
        request.attachment_resource_refs
    ):
        raise ValueError("Duplicate resource references")
    if request.publication == "draft" and (
        request.gradebook.mode != "none" or request.calendar_deadline != "none"
    ):
        raise ValueError("Explicit draft cannot create integrations")
