"""Default facades against source-derived wire fixtures; no live academic writes."""

from copy import deepcopy
from dataclasses import replace

import pytest

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.errors import SakaiError
from tests.fixtures.five_tool_http import SUBMISSION, FiveToolHTTP
from tests.fixtures.sakai import FakeOBO, principal


@pytest.mark.asyncio
@pytest.mark.parametrize("grader", [True, False])
async def test_own_grade_uses_current_student_page_and_never_aggregate_for_grader(
    grader,
):
    wire = FiveToolHTTP()
    if not grader:
        wire.functions = ["gradebook.viewOwnGrades"]
    client = wire.client()
    result = await client.courses.get_my_grades(principal(), "course-a")
    assert result == [
        {"itemId": 7, "title": "Synthetic Quiz", "score": "8.5", "pointsPossible": 10.0}
    ]
    paths = [r.url.path for r in wire.calls]
    assert ("/api/sites/course-a/grades" in paths) == (not grader)
    assert "/portal/tool/gradebook-p/gradebook" in paths
    assert wire.calls[-1].headers.get("x-mcp-flow-end") == "1"
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "wrong-eid",
        "no-own-permission",
        "duplicate-title",
        "wrong-item",
        "unreleased",
        "bad-locale",
    ],
)
async def test_own_grade_identity_permission_and_mapping_errors_fail_closed(failure):
    wire = FiveToolHTTP()
    if failure == "wrong-eid":
        wire.native_eid = "wrong-eid"
    if failure == "no-own-permission":
        wire.functions = ["asn.grade"]
    if failure == "duplicate-title":
        wire.grade_items.append({**wire.grade_items[0], "id": 8})
    if failure == "wrong-item":
        wire.grade_items[0]["name"] = "Other Quiz"
    if failure == "unreleased":
        wire.grade_items[0]["released"] = False
    if failure == "bad-locale":
        wire.grade_html = wire.grade_html.replace("/ 10.0", "/ 10,0")
    with pytest.raises(SakaiError):
        await wire.client().courses.get_my_grades(principal(), "course-a")
    assert not wire.posts


@pytest.mark.asyncio
async def test_default_submission_reads_preserve_identity_text_and_units_without_invented_flags():
    wire = FiveToolHTTP()
    client = wire.client()
    metadata = await client.assignments.get_course_submissions(
        principal(), "course-a", "assignment-a"
    )
    assert metadata == [
        {"id": "submission-a", "submitterIds": ["student-a"], "submittedAt": 1790000000}
    ]
    page = await client.grading.list_assignment_submissions(
        principal(),
        native.ListAssignmentSubmissionsRequest(
            course_id="course-a", assignment_id="assignment-a"
        ),
    )
    assert page.completeness.complete is False
    assert page.items[0].flags is None and page.items[0].attempt_count is None
    assert page.items[0].attachments_complete is False
    result = await client.grading.get_assignment_submission(
        principal(),
        native.GetAssignmentSubmissionRequest(
            course_id="course-a",
            assignment_id="assignment-a",
            submission_id="submission-a",
        ),
    )
    assert result.inline_text == SUBMISSION["submittedText"]
    assert "DO NOT EXPOSE" not in result.model_dump_json()
    data, mime, sha = await client.grading.read_grading_file(
        principal(),
        "course-a",
        "assignment-a",
        "submission-a",
        "inline",
        result.submission.content_revision,
    )
    assert (
        data == SUBMISSION["submittedText"].encode()
        and mime == "text/html"
        and len(sha) == 64
    )
    assert not wire.posts


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "group-only",
        "anonymous",
        "group-submission",
        "wrong-assignment",
        "duplicate-submission",
        "omitted-attachment-list",
    ],
)
async def test_submission_scope_and_serializer_failures_are_explicit(failure):
    wire = FiveToolHTTP()
    if failure == "group-only":
        wire.functions = ["asn.grade.groups"]
    if failure == "anonymous":
        wire.assignment["anonymousGrading"] = True
    if failure == "group-submission":
        wire.assignment["submissions"][0]["groupId"] = "group-b"
    if failure == "wrong-assignment":
        wire.assignment["submissions"][0]["gradableId"] = "other-assignment"
    if failure == "duplicate-submission":
        wire.assignment["submissions"].append(deepcopy(SUBMISSION))
    if failure == "omitted-attachment-list":
        wire.assignment["submissions"][0].pop("submittedAttachments")
    with pytest.raises(SakaiError):
        await wire.client().assignments.get_course_submissions(
            principal(), "course-a", "assignment-a"
        )
    if failure in {"group-only", "anonymous", "group-submission"}:
        assert not any(r.url.path.startswith("/direct/assignment/") for r in wire.calls)


@pytest.mark.asyncio
async def test_observed_submission_paging_conflicts_on_change_and_missing_row_is_not_a_false_empty():
    wire = FiveToolHTTP()
    client = wire.client()
    wire.assignment["submissions"].append(
        {**deepcopy(SUBMISSION), "id": "submission-b"}
    )
    request = native.ListAssignmentSubmissionsRequest(
        course_id="course-a", assignment_id="assignment-a", limit=1
    )
    first = await client.grading.list_assignment_submissions(principal(), request)
    wire.assignment["submissions"][0]["submittedText"] = "Changed"
    with pytest.raises(SakaiError, match="CONFLICT"):
        await client.grading.list_assignment_submissions(
            principal(), request.model_copy(update={"cursor": first.next_cursor})
        )
    with pytest.raises(SakaiError, match="UNSUPPORTED_CAPABILITY"):
        await client.grading.get_assignment_submission(
            principal(),
            native.GetAssignmentSubmissionRequest(
                course_id="course-a",
                assignment_id="assignment-a",
                submission_id="omitted",
            ),
        )
    wire.assignment["submissions"] = []
    # Native no-submission rows have no stable identity marker. Without positive
    # individual-mode evidence, do not hydrate and manufacture an empty result.
    before = sum(r.url.path.startswith("/direct/assignment/") for r in wire.calls)
    with pytest.raises(SakaiError, match="UNSUPPORTED_CAPABILITY"):
        await client.grading.list_assignment_submissions(principal(), request)
    assert (
        sum(r.url.path.startswith("/direct/assignment/") for r in wire.calls) == before
    )


@pytest.mark.asyncio
async def test_announcement_create_sends_once_with_literal_safe_content_and_durable_readback():
    wire = FiveToolHTTP()
    client = wire.client()
    title, body = "Literal &copy; <tag>", "First & <b>\nSecond"
    result = await client.announcements.create_course_announcement(
        principal(), "course-a", title, body
    )
    assert result["id"] == "created-once" and result["title"] == title
    assert result["verification"]["causation_guaranteed"] is False
    assert wire.posts == 1
    journal = client.announcements.creation.journal
    records = list(journal.records.store._objects.values())
    assert len(records) == 1
    import json

    saved = json.loads(records[0].data)
    assert saved["value"]["phase"] == "observed"
    assert saved["value"]["request"]["body"] == body
    assert not any(
        "sakai_csrf_token" in str(saved["value"][k])
        for k in ["request", "observations"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "500", "validation", "bad-html"])
async def test_announcement_unknowns_never_replay_native_post_and_keep_receipt(failure):
    wire = FiveToolHTTP()
    wire.failure = failure
    client = wire.client()
    with pytest.raises(SakaiError, match="AMBIGUOUS_WRITE_OUTCOME"):
        await client.announcements.create_course_announcement(
            principal(), "course-a", "Title", "Body"
        )
    assert wire.posts == 1
    import json

    saved = json.loads(
        next(
            iter(client.announcements.creation.journal.records.store._objects.values())
        ).data
    )
    assert (
        saved["value"]["phase"] == "unknown" and saved["value"]["ever_unknown"] is True
    )
    assert any(r.headers.get("x-mcp-flow-end") for r in wire.calls)


@pytest.mark.asyncio
async def test_announcement_without_durable_store_or_permission_sends_no_post():
    wire = FiveToolHTTP()
    with pytest.raises(SakaiError, match="DEPENDENCY_UNAVAILABLE"):
        await wire.client(with_store=False).announcements.create_course_announcement(
            principal(), "course-a", "Title", "Body"
        )
    assert not wire.calls
    wire.functions = ["gradebook.viewOwnGrades"]
    with pytest.raises(SakaiError, match="FORBIDDEN"):
        await wire.client().announcements.create_course_announcement(
            principal(), "course-a", "Title", "Body"
        )
    assert not wire.posts


@pytest.mark.asyncio
async def test_obo_identity_change_inside_browser_flow_blocks_native_page():
    wire = FiveToolHTTP()
    client = wire.client()

    class ChangedOBO(FakeOBO):
        async def acquire(self, token):
            return replace(await super().acquire(token), sakai_eid="changed-eid")

    client.browser_transport.obo = ChangedOBO()
    with pytest.raises(SakaiError, match="UNAUTHENTICATED"):
        await client.courses.get_my_grades(principal(), "course-a")
    assert not any(r.url.path.startswith("/portal/") for r in wire.calls)
