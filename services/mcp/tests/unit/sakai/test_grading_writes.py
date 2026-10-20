"""Default public grading facade over existing HTTP; no legacy business fallback."""

import pytest

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts.submissions import entry
from sakai_mcp.errors import SakaiError
from sakai_mcp.grading.serialization import digest, payload_hash
from sakai_mcp.workflows.captures import assignment_revision
from sakai_mcp.workflows.grading import GradingWorkflow
from tests.fixtures.grading_http import GradingHTTP
from tests.fixtures.grading_requests import save_request
from tests.fixtures.sakai import principal


async def request(client, kind="save"):
    _, assignment, rows = await client.submissions.source(
        principal(), "course-a", "assignment-a"
    )
    item = entry(rows[0], assignment)
    value = save_request()
    value["expected_assignment_revision"] = assignment_revision(assignment)
    value["grades"][0].update(
        expected_content_revision=item.content_revision,
        expected_grade_revision=item.grade_revision,
    )
    if kind == "release":
        value["operation_id"] = "00000000-0000-0000-0000-000000000002"
        value["grades"][0].pop("score")
        value["grades"][0].pop("feedback")
        value["grades"][0].update(
            expected_score=item.score,
            expected_feedback_sha256=digest(rows[0].feedbackComment.encode())
            if rows[0].feedbackComment
            else None,
        )
    value["payload_sha256"] = payload_hash(
        kind,
        value["course_id"],
        value["assignment_id"],
        value["expected_assignment_revision"],
        value["grades"],
    )
    return (
        native.SaveAssignmentGradesRequest
        if kind == "save"
        else native.ReleaseAssignmentGradesRequest
    ).model_validate(value)


@pytest.mark.asyncio
async def test_prepare_save_and_release_preserve_side_fields_and_receipts():
    w = GradingHTTP()
    c = w.client()
    row = w.assignment["submissions"][0]
    row.update(
        privateNotes="Keep private",
        feedbackText="Keep inline",
        feedbackComment="Keep feedback",
        properties={
            "allow_resubmit_number": "2",
            "allow_resubmit_closeTime": "1793000000000",
            "allow_extension_closeTime": "1794000000000",
            "other": "unchanged",
        },
    )
    req = await request(c)
    prepared = await GradingWorkflow(c).prepare_grade_payload(
        principal(),
        req.course_id,
        req.assignment_id,
        "save",
        req.operation_id,
        req.expected_assignment_revision,
        req.grades,
    )
    assert prepared.validation.outcome == "validated" and not w.grade_posts
    assert not c.grading.operations.store().store._objects
    saved = await c.grading.save_assignment_grades(
        principal(), prepared.commit_arguments
    )
    assert saved.outcome == "partial" and saved.rows[0].stage == "saved"
    assert (
        len(w.grade_posts) == 1
        and row["privateNotes"] == "Keep private"
        and row["properties"]["other"] == "unchanged"
    )
    returned = await c.grading.release_assignment_grades(
        principal(), await request(c, "release")
    )
    assert (
        returned.outcome == "partial"
        and returned.rows[0].returned
        and returned.rows[0].grade_released
    )
    assert len(w.grade_posts) == 2 and all(
        "/api/mcp/v1/" not in r.url.path for r in w.calls
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "legacy-revision",
        "notes",
        "properties",
        "score",
        "grade-revision",
        "content-revision",
        "group",
        "linked",
        "permission",
        "duplicate",
        "no-store",
    ],
)
async def test_unsupported_or_stale_inputs_fail_before_grade_post(failure):
    w = GradingHTTP()
    c = w.client()
    req = await request(c)
    if failure == "legacy-revision":
        req.expected_assignment_revision = "legacy-native-hash"
    if failure == "notes":
        w.assignment["submissions"][0]["privateNotes"] = "<p>rich</p>"
    if failure == "properties":
        w.assignment["submissions"][0].pop("properties")
    if failure == "score":
        req.grades[0].score = "4.25"
    if failure == "grade-revision":
        req.grades[0].expected_grade_revision = "stale"
    if failure == "content-revision":
        req.grades[0].expected_content_revision = "stale"
    if failure == "group":
        w.assignment["submissions"][0]["groupId"] = "group-a"
    if failure == "linked":
        w.models["assignment-a"]["new_assignment_send_to_gradebook"] = "true"
    if failure == "permission":
        w.functions = ["asn.grade"]
    if failure == "duplicate":
        req.grades.append(req.grades[0])
    if failure == "no-store":
        c.grading.operations.records = None
    req.payload_sha256 = payload_hash(
        "save",
        req.course_id,
        req.assignment_id,
        req.expected_assignment_revision,
        [r.model_dump() for r in req.grades],
    )
    with pytest.raises(SakaiError):
        await c.grading.save_assignment_grades(principal(), req)
    assert not w.grade_posts


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["503", "lost", "malformed", "side-field"])
async def test_uncertain_posts_are_single_send_and_remain_unknown(failure):
    w = GradingHTTP()
    c = w.client()
    req = await request(c)
    w.grade_failure = failure
    with pytest.raises(SakaiError, match="AMBIGUOUS_WRITE_OUTCOME"):
        await c.grading.save_assignment_grades(principal(), req)
    read = await c.grading.get_assignment_grading_operation(
        principal(),
        native.GetAssignmentGradingOperationRequest(
            course_id=req.course_id,
            assignment_id=req.assignment_id,
            operation_id=req.operation_id,
        ),
    )
    assert read.outcome == "unknown" and len(w.grade_posts) == 1
    # A repeat may conflict with changed observations; it must never replay a send.
    try:
        await c.grading.save_assignment_grades(principal(), req)
    except SakaiError:
        pass
    assert len(w.grade_posts) == 1
