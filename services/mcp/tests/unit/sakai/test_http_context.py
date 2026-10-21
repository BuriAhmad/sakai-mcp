"""Actual context facade over existing HTTP, with role/state/identity negatives."""

import pytest

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.errors import SakaiError
from tests.fixtures.context_http import ContextHTTP
from tests.fixtures.sakai import principal


async def read(wire):
    return await wire.client().grading.get_assignment_grading_context(
        principal(),
        native.GetAssignmentGradingContextRequest(
            course_id="course-a", assignment_id="assignment-a"
        ),
    )


@pytest.mark.asyncio
async def test_context_uses_raw_observed_state_without_student_data_or_guessed_roster():
    wire = ContextHTTP()
    result = await read(wire)
    assert result.assignment.scale_factor == 100
    assert result.assignment.max_points == "10"
    assert result.assignment.native_release_grades is False
    assert result.assignment.open_at == "2026-10-01T00:00:00.123456789Z"
    assert result.assignment.configuration_revision.startswith("httpctx1-")
    assert not result.completeness.complete and not result.supported.prepare
    assert result.submission_summary.expected_students is None
    assert "PRIVATE" not in result.model_dump_json()
    assert all("/api/mcp/" not in r.url.path for r in wire.calls)
    assert not wire.grade_posts


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "missing", ["asn.grade", "asn.new", "asn.revise", "gradebook.editAssignments"]
)
async def test_missing_authority_blocks_raw_helper(missing):
    wire = ContextHTTP()
    wire.functions.remove(missing)
    with pytest.raises(SakaiError):
        await read(wire)
    assert all("/annc/" not in r.url.path for r in wire.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field,value",
    [
        ("scaleFactor", None),
        ("scaleFactor", True),
        ("releaseGrades", None),
        ("releaseGrades", "false"),
        ("context", "foreign"),
        ("maxGradePoint", 900),
        ("attachments", ["/content/attachment/opaque"]),
        ("deleted", True),
    ],
)
async def test_unknown_or_inconsistent_raw_state_is_rejected(field, value):
    wire = ContextHTTP()
    wire.raw[field] = value
    with pytest.raises(SakaiError):
        await read(wire)
    assert not wire.grade_posts
