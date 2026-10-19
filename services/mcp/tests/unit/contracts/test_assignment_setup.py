import pytest
from pydantic import ValidationError

from sakai_mcp.contracts.assignment_setup_validation import (
    validate_create,
    validate_window,
)
from tests.fixtures.assignment_setup import request


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
