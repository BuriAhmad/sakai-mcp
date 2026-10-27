"""Selected public grade facade, explicit native release and unavailable projection."""

import httpx
import pytest

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.errors import SakaiError
from tests.fixtures.five_tool_http import FiveToolHTTP, gradebook_table
from tests.fixtures.sakai import principal


def request():
    return native.GetAssignmentGradesRequest(
        course_id="course-a",
        assignment_id="assignment-a",
        rows=[native.Target(submission_id="submission-a", sakai_user_id="student-a")],
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("released", [False, True])
@pytest.mark.parametrize("score", ["", "0", "8.50"])
async def test_selected_assignment_read_never_substitutes_a_gradebook_value(
    released, score
):
    wire = FiveToolHTTP()
    wire.assignment["submissions"][0].update(
        gradeReleased=released,
        grade=score,
        graded=True,
        returned=False,
        feedbackComment="Literal & <feedback>",
    )
    client = wire.client()
    result = await client.grading.get_assignment_grades(principal(), request())
    row = result.rows[0]
    assert row.score == (score or None)
    assert row.flags.grade_released is released and row.flags.returned is False
    assert row.feedback_sha256 is not None and row.returned_at is None
    assert row.gradebook_score is None and row.gradebook_state == "unavailable"
    assert result.gradebook.mode == "unknown" and not result.gradebook.available
    assert result.completeness.complete is False and row.grade_revision.startswith(
        "http1-"
    )
    assert all(r.method == "GET" for r in wire.calls)
    old = row.grade_revision
    wire.assignment["submissions"][0]["gradeReleased"] = not released
    assert (await client.grading.get_assignment_grades(principal(), request())).rows[
        0
    ].grade_revision != old


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "permission",
        "group-only",
        "eid",
        "anonymous",
        "group",
        "wrong-user",
        "duplicate",
        "score-format",
        "nonpoint",
        "cross-assignment",
    ],
)
async def test_selected_scope_identity_and_point_contract(failure):
    wire = FiveToolHTTP()
    req = request()
    if failure == "permission":
        wire.functions = []
    if failure == "group-only":
        wire.functions = ["asn.grade.groups"]
    if failure == "eid":
        wire.native_eid = "foreign"
    if failure == "anonymous":
        wire.assignment["anonymousGrading"] = True
    if failure == "group":
        wire.assignment["submissions"][0]["groupId"] = "other"
    if failure == "wrong-user":
        req.rows[0].sakai_user_id = "other"
    if failure == "duplicate":
        req.rows.append(req.rows[0])
    if failure == "score-format":
        wire.assignment["submissions"][0]["grade"] = "8,5"
    if failure == "nonpoint":
        wire.assignment["gradeScale"] = "LETTER_GRADE_TYPE"
    if failure == "cross-assignment":
        wire.assignment["submissions"][0]["gradableId"] = "foreign"
    with pytest.raises(SakaiError):
        await wire.client().grading.get_assignment_grades(principal(), req)
    assert not wire.posts
    if failure in {"permission", "group-only", "anonymous", "group"}:
        assert not any(r.url.path.startswith("/direct/assignment/") for r in wire.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "missing-cell",
        "foreign-ref",
        "unknown-indicator",
        "duplicate-row",
        "permission-error",
        "server-error",
        "release-race",
    ],
)
async def test_native_page_contract_errors_and_release_race_fail_without_fallback(
    failure,
):
    wire = FiveToolHTTP()
    client = wire.client()
    count = 0

    def handler(req):
        nonlocal count
        if req.url.path == "/direct/assignment/item/assignment-a.json":
            if failure == "permission-error":
                return httpx.Response(403)
            if failure == "server-error":
                return httpx.Response(500)
        response = wire(req)
        if "eventSubmit_doGrade_assignment" in req.url.params:
            count += 1
            content = response.content
            if failure == "missing-cell":
                content = content.replace(
                    b'headers="gradereleased"', b'headers="other"'
                )
            if failure == "foreign-ref":
                content = content.replace(
                    b"%2Fs%2Fcourse-a%2Fassignment-a", b"%2Fs%2Fother%2Fassignment-a"
                )
            if failure == "unknown-indicator":
                content = content.replace(
                    b'<td headers="gradereleased">',
                    b'<td headers="gradereleased"><span class="unknown"/>',
                )
            if failure == "duplicate-row":
                content = content.replace(
                    b"</table>", content.split(b'<table id="submissionList">')[1]
                )
            if failure == "release-race" and count == 2:
                content = content.replace(
                    b'<td headers="gradereleased">',
                    b'<td headers="gradereleased"><span class="si si-check"/>',
                )
            return httpx.Response(
                200, content=content, headers={"content-type": "text/html"}
            )
        return response

    shared = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client.existing_transport._http = shared
    client.browser_transport._http = shared
    with pytest.raises(SakaiError):
        await client.grading.get_assignment_grades(principal(), request())
    assert not wire.posts


INSTRUCTOR = [
    "gradebook.gradeAll",
    "gradebook.editAssignments",
    "section.role.instructor",
]


def with_gradebook(
    wire, table, *, form_site="course-a", form_guid="course-a", status=200
):
    import json

    from tests.fixtures.five_tool_http import page

    def handler(req):
        if req.url.path == "/portal/tool/gradebook-p/grades":
            wire.calls.append(req)
            if status != 200:
                return httpx.Response(status)
            return page(
                f'<form data-site-id="{form_site}" data-guid="{form_guid}"></form>'
                "<script>var tableData = " + json.dumps(table) + ";</script>"
            )
        return wire(req)

    client = wire.client()
    shared = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client.existing_transport._http = shared
    client.browser_transport._http = shared
    return client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "serialized,expected,warning",
    [
        ("json:[null,99,null,7.25]", "7.25", "gradebook_representation_json-double"),
        ("json:[null,99,null,0]", "0", "gradebook_representation_json-double"),
        ("json:[null,99,null,null]", None, "gradebook_representation_json-double"),
        ("packed:f2N/wAcZ", "7.25", "display-rounded-to-hundredths"),
    ],
)
async def test_independent_gradebook_display_through_default(
    serialized, expected, warning
):
    wire = FiveToolHTTP()
    wire.functions += INSTRUCTOR
    wire.assignment["submissions"][0]["grade"] = "8.50"
    table = gradebook_table()
    table["serializedGrades"] = serialized
    result = await with_gradebook(wire, table).grading.get_assignment_grades(
        principal(), request()
    )
    assert result.rows[0].score == "8.50"
    assert result.rows[0].gradebook_score == expected
    assert result.rows[0].gradebook_state == "available"
    assert result.rows[0].gradebook_comment_sha256 is None
    assert result.gradebook.item_id == "7" and result.gradebook.mode == "external"
    assert result.gradebook.released is False and result.gradebook.counted is True
    assert not result.completeness.complete and warning in result.warnings
    assert "gradebook_comment_bytes_unavailable" in result.completeness.reasons
    assert all(r.method == "GET" for r in wire.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("missing", INSTRUCTOR)
async def test_gradebook_table_not_opened_without_each_authority(missing):
    wire = FiveToolHTTP()
    wire.functions += [f for f in INSTRUCTOR if f != missing]
    result = await wire.client().grading.get_assignment_grades(principal(), request())
    assert result.rows[0].gradebook_state == "unavailable"
    assert not any(
        r.url.path.startswith("/portal/tool/gradebook-p") for r in wire.calls
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "site",
        "group-gradebook",
        "settings-guid",
        "percentage",
        "title-only",
        "foreign-app",
        "internal",
        "duplicate-column",
        "missing-user",
        "duplicate-user",
        "release-type",
        "negative",
        "huge-exponent",
        "tiny-exponent",
        "nan",
        "fraction-carry",
        "403",
        "500",
    ],
)
async def test_gradebook_binding_precision_and_errors_fail_closed(failure):
    wire = FiveToolHTTP()
    wire.functions += INSTRUCTOR
    table = gradebook_table()
    options = {}
    col = table["columns"][1]
    if failure == "site":
        options["form_site"] = "foreign"
    if failure == "group-gradebook":
        options["form_guid"] = "group-a"
    if failure == "settings-guid":
        table["settings"]["gUid"] = "foreign"
    if failure == "percentage":
        table["settings"]["isPointsGradeEntry"] = False
    if failure == "title-only":
        col["externalId"] = "other"
    if failure == "foreign-app":
        col["externalAppName"] = "other"
    if failure == "internal":
        col["externallyMaintained"] = False
    if failure == "release-type":
        col["released"] = "false"
    if failure == "duplicate-column":
        table["columns"][0] = dict(col)
    if failure == "missing-user":
        table["students"][1]["userId"] = "foreign"
    if failure == "duplicate-user":
        table["students"][0]["userId"] = "student-a"
    if failure == "negative":
        table["serializedGrades"] = "json:[null,99,null,-1]"
    if failure == "huge-exponent":
        table["serializedGrades"] = "json:[null,99,null,1e1000000]"
    if failure == "tiny-exponent":
        table["serializedGrades"] = "json:[null,99,null,1e-1000000]"
    if failure == "nan":
        table["serializedGrades"] = "json:[null,99,null,NaN]"
    if failure == "fraction-carry":
        table["serializedGrades"] = "packed:f2N/wAdk"
    if failure in {"403", "500"}:
        options["status"] = int(failure)
    with pytest.raises(SakaiError):
        await with_gradebook(wire, table, **options).grading.get_assignment_grades(
            principal(), request()
        )
    assert not wire.posts


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", [None, "repeat", "missing-pager", "duplicate", "race"]
)
async def test_selected_rows_follow_rendered_native_grading_pages(failure):
    from tests.fixtures.five_tool_http import page

    wire = FiveToolHTTP()
    client = wire.client()
    round_count = 0

    def handler(req):
        nonlocal round_count
        if (
            req.url.path == "/portal/tool/assignments-p"
            and "eventSubmit_doGrade_assignment" in req.url.params
        ):
            round_count += 1
            original = wire(req).content
            if failure == "missing-pager":
                return page(original.decode().split("<input")[0])
            if failure == "duplicate":
                original = original.replace(
                    b'<input name="eventSubmit_doList_next" disabled>', b""
                )
            else:
                # Actual native no-submission branch has no UID/photo/link.
                original = b'<table id="submissionList"><tr><td headers="studentname">Missing Student</td></tr></table>'
            control = '<input name="eventSubmit_doList_next" onclick="VM_PP.doPageNav(\'/portal/tool/assignments-p?eventSubmit_doList_next=\',this)">'
            return page(original.decode() + control)
        if (
            req.url.path == "/portal/tool/assignments-p"
            and "eventSubmit_doList_next" in req.url.params
        ):
            wire.calls.append(req)
            # Reuse the source-derived submitted-row render without recording a fake request.
            response = wire(
                httpx.Request(
                    "GET",
                    "https://sakai.example.test/portal/tool/assignments-p?eventSubmit_doGrade_assignment=",
                    headers=req.headers,
                )
            )
            wire.calls.pop()
            if failure == "repeat":
                return page(
                    '<table id="submissionList"><tr><td headers="studentname">Missing Student</td></tr></table><input name="eventSubmit_doList_next" onclick="VM_PP.doPageNav(\'/portal/tool/assignments-p?eventSubmit_doList_next=\',this)">'
                )
            if failure == "race" and round_count == 2:
                return page(
                    response.text.replace(
                        '<td headers="gradereleased">',
                        '<td headers="gradereleased"><span class="si-check"/>',
                    )
                )
            return response
        return wire(req)

    shared = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client.existing_transport._http = shared
    client.browser_transport._http = shared
    if failure:
        with pytest.raises(SakaiError):
            await client.grading.get_assignment_grades(principal(), request())
    else:
        result = await client.grading.get_assignment_grades(principal(), request())
        assert len(result.rows) == 1 and not result.completeness.complete
        assert sum("eventSubmit_doList_next" in r.url.params for r in wire.calls) == 2
    assert not wire.posts
