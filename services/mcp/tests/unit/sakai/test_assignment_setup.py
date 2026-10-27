import asyncio

import pytest
from pydantic import ValidationError

from sakai_mcp.contracts.assignment_setup import (
    PublishAssignmentRequest,
)
from sakai_mcp.errors import ErrorCode, SakaiError
from tests.fixtures.assignment_setup import adapter, request
from tests.fixtures.sakai import principal
from tests.fixtures.setup_http import SetupHTTP


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


def revision(result):
    return next(
        w.removeprefix("configuration_revision: ")
        for w in result.warnings
        if w.startswith("configuration_revision: ")
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("publication", ["draft", "published"])
@pytest.mark.parametrize(
    "submission",
    [
        "text_only",
        "attachments_only",
        "text_and_attachments",
        "non_electronic",
        "single_attachment",
    ],
)
async def test_create_default_facade_observes_real_native_identity_and_fields(
    publication, submission
):
    wire = SetupHTTP()
    result = await wire.client().assignments.create_assignment(
        principal(), request(publication=publication, submission_type=submission)
    )
    model = wire.models[result.assignment_id]
    assert model["draft"] is (publication == "draft")
    assert model["new_assignment_title"] == "Assignment 3"
    assert model["new_assignment_instructions"] == "Submit a report and source archive."
    assert model["new_assignment_open_"] == "2026-10-12T09:00"
    assert model["new_assignment_grade_points"] == "100.0"
    assert wire.posts == 1 and result.outcome == "partial"
    assert result.assignment is None and result.failure.retry_safe is False
    assert (
        revision(result).startswith("http1-")
        and result.gradebook.status == "not_requested"
    )
    assert not any(r.url.path.startswith("/direct/assignment") for r in wire.calls)


@pytest.mark.asyncio
async def test_create_then_publish_preserves_configuration_and_uses_observed_revision():
    wire = SetupHTTP()
    client = wire.client()
    first = await client.assignments.create_assignment(
        principal(),
        request(publication="draft", instructions="<p>Literal &amp; content</p>"),
    )
    before = dict(wire.models[first.assignment_id])
    result = await client.assignments.publish_assignment(
        principal(),
        PublishAssignmentRequest(
            course_id="course-a",
            assignment_id=first.assignment_id,
            expected_assignment_revision=revision(first),
            gradebook={"mode": "none"},
            calendar_deadline="none",
        ),
    )
    assert result.assignment_id == first.assignment_id and wire.posts == 2
    assert wire.models[first.assignment_id] == {**before, "draft": False}
    assert result.outcome == "partial" and result.verified_at is not None
    with pytest.raises(SakaiError, match="CONFLICT"):
        await client.assignments.publish_assignment(
            principal(),
            PublishAssignmentRequest(
                course_id="course-a",
                assignment_id=first.assignment_id,
                expected_assignment_revision=revision(result),
                gradebook={"mode": "none"},
                calendar_deadline="none",
            ),
        )
    assert wire.posts == 2


@pytest.mark.asyncio
async def test_context_reads_no_submission_bodies_and_provides_metadata_revision_for_publish():
    import json

    wire = SetupHTTP()
    wire.seed()
    context = await wire.client().assignments.get_course_assessment_context(
        principal(), "course-a"
    )
    assert (
        context.course.id == "course-a" and context.course.title == "Synthetic Course"
    )
    assert (
        context.course.timezone == "Asia/Karachi"
        and context.course.timezone_source == "unknown"
    )
    assert context.complete is False and context.assignments == []
    assert (
        context.sections.assignments.status == "unavailable"
        and context.sections.calendar.status == "unavailable"
    )
    assert context.gradebook.available and context.gradebook.items[0].id == "7"
    assert context.gradebook.items[0].max_points == 10.0
    assert not any(
        r.url.path.startswith("/portal/tool/gradebook-p") for r in wire.calls
    )
    metadata = json.loads(
        next(
            w.removeprefix("assignment_metadata_only: ")
            for w in context.warnings
            if w.startswith("assignment_metadata_only: ")
        )
    )
    assert metadata["id"] == "assignment-a" and metadata["draft"] is True
    assert metadata["configuration_revision"].startswith("http1-")
    result = await wire.client().assignments.publish_assignment(
        principal(),
        PublishAssignmentRequest(
            course_id="course-a",
            assignment_id="assignment-a",
            expected_assignment_revision=metadata["configuration_revision"],
            gradebook={"mode": "none"},
            calendar_deadline="none",
        ),
    )
    assert result.assignment_id == "assignment-a" and wire.posts == 1
    assert not any(r.url.path.startswith("/direct/assignment") for r in wire.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize("with_category", [False, True])
async def test_native_default_external_gradebook_policy_is_independently_read_back(
    with_category,
):
    wire = SetupHTTP()
    wire.categories = with_category
    result = await wire.client().assignments.create_assignment(
        principal(),
        request(
            gradebook={
                "mode": "new_external",
                "category_id": "5" if with_category else None,
                "release_to_students": True,
                "count_toward_course_grade": True,
            }
        ),
    )
    assert wire.posts == 1
    assert (
        result.gradebook.mode == "new_external" and result.gradebook.status == "linked"
    )
    assert (
        result.gradebook.external_id == "/assignment/a/course-a/" + result.assignment_id
    )
    assert result.gradebook.category_id == ("5" if with_category else None)
    assert result.gradebook.released is True and result.gradebook.counted is True
    assert (
        result.outcome == "partial"
    )  # Do not invent the remaining strict Assignment fields.


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"title": "x" * 101},
        {"title": "😀" * 51},
        {"instructions": "x" * 65536},
        {
            "gradebook": {
                "mode": "new_external",
                "category_id": "-1",
                "release_to_students": True,
                "count_toward_course_grade": True,
            }
        },
        {"calendar_deadline": "course_calendar"},
        {"attachment_resource_refs": ["/content/group/course-a/brief.pdf"]},
        {"resubmission": {"count": 11, "until": "2026-10-27T09:00:00+05:00"}},
        {"open_at": "2026-10-12T09:00:01+05:00"},
        {
            "gradebook": {
                "mode": "new_external",
                "category_id": None,
                "release_to_students": False,
                "count_toward_course_grade": True,
            }
        },
        {
            "gradebook": {
                "mode": "new_external",
                "category_id": None,
                "release_to_students": True,
                "count_toward_course_grade": False,
            }
        },
    ],
)
async def test_unsupported_policies_fail_before_http(changes):
    wire = SetupHTTP()
    with pytest.raises(SakaiError, match="UNSUPPORTED_CAPABILITY"):
        await wire.client().assignments.create_assignment(
            principal(), request(**changes)
        )
    assert not wire.calls and not wire.posts


@pytest.mark.asyncio
async def test_unconfigured_store_and_disabled_feature_make_no_http_calls():
    for options in ({"with_store": False}, {"enabled": False}):
        wire = SetupHTTP()
        with pytest.raises(SakaiError):
            await wire.client(**options).assignments.create_assignment(
                principal(), request()
            )
        assert not wire.calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "permission",
        "group-only",
        "foreign-identity",
        "anonymous",
        "calendar-default",
        "peer",
        "review",
        "rubric",
        "attachments",
        "group-gradebooks",
    ],
)
async def test_permissions_identity_and_unsupported_native_state_never_send(failure):
    wire = SetupHTTP()
    if failure == "permission":
        wire.functions.remove("asn.new")
    if failure == "group-only":
        wire.functions = ["asn.new", "asn.revise.groups"]
    if failure == "foreign-identity":
        wire.native_eid = "foreign"
    if failure in {"anonymous", "calendar-default", "peer", "review"}:
        key = {
            "anonymous": "new_assignment_check_anonymous_grading",
            "calendar-default": "new_assignment_check_add_due_date",
            "peer": "new_assignment_use_peer_assessment",
            "review": "new_assignment_use_review_service",
        }[failure]
        wire.form_extras = f'<input type="checkbox" name="{key}" checked disabled>'
    if failure == "rubric":
        wire.form_extras = '<sakai-rubric-association association="{&quot;rubricId&quot;:1}"></sakai-rubric-association>'
    if failure == "attachments":
        wire.form_extras = (
            '<input name="attachments" value="/content/attachment/unknown">'
        )
    if failure == "group-gradebooks":
        wire.form_extras = "<sakai-multi-gradebook></sakai-multi-gradebook>"
    with pytest.raises(SakaiError):
        await wire.client().assignments.create_assignment(principal(), request())
    assert not wire.posts and not any(
        r.url.path.startswith("/direct/assignment") for r in wire.calls
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "500", "unknown", "validation", "403"])
async def test_uncertain_or_denied_write_is_not_replayed(failure):
    wire = SetupHTTP()
    wire.failed = failure
    with pytest.raises(SakaiError) as error:
        await wire.client().assignments.create_assignment(principal(), request())
    assert wire.posts == 1
    assert error.value.code == (
        ErrorCode.FORBIDDEN if failure == "403" else ErrorCode.AMBIGUOUS_WRITE_OUTCOME
    )


@pytest.mark.asyncio
async def test_native_timezone_conversion_visibility_and_resubmissions_are_verified():
    wire = SetupHTTP()
    wire.zone = "UTC"
    result = await wire.client().assignments.create_assignment(
        principal(),
        request(
            visible_at="2026-10-11T09:00:00+05:00",
            resubmission={"count": 2, "until": "2026-10-27T09:00:00+05:00"},
        ),
    )
    model = wire.models[result.assignment_id]
    assert model["new_assignment_open_"] == "2026-10-12T04:00"
    assert model["new_assignment_visible_"] == "2026-10-11T04:00"
    assert (
        model["allow_resubmit_close_"] == "2026-10-27T04:00"
        and model["allow_resubmit_number"] == "2"
    )


@pytest.mark.asyncio
async def test_publish_rejects_stale_revision_without_writing():
    wire = SetupHTTP()
    wire.seed()
    with pytest.raises(SakaiError, match="CONFLICT"):
        await wire.client().assignments.publish_assignment(
            principal(),
            PublishAssignmentRequest(
                course_id="course-a",
                assignment_id="assignment-a",
                expected_assignment_revision="revision-a",
                gradebook={"mode": "none"},
                calendar_deadline="none",
            ),
        )
    assert not wire.posts


@pytest.mark.asyncio
async def test_optional_create_defaults_are_disabled_and_category_is_not_inherited():
    wire = SetupHTTP()
    wire.new_defaults = {
        "new_assignment_check_auto_announce": True,
        "new_assignment_check_add_due_date": True,
        "new_assignment_category": "5",
    }
    result = await wire.client().assignments.create_assignment(
        principal(),
        request(
            gradebook={
                "mode": "new_external",
                "category_id": None,
                "release_to_students": True,
                "count_toward_course_grade": True,
            }
        ),
    )
    sent = next(r for r in wire.calls if r.method == "POST")
    from urllib.parse import parse_qs

    fields = parse_qs(sent.content.decode(), keep_blank_values=True)
    assert (
        "new_assignment_check_auto_announce" not in fields
        and "new_assignment_check_add_due_date" not in fields
    )
    assert "new_assignment_category" not in fields
    assert result.gradebook.category_id is None and result.gradebook.status == "linked"


@pytest.mark.asyncio
async def test_durable_sending_precedes_http_and_uncertain_outcome_is_retained():
    import json

    import httpx

    wire = SetupHTTP()
    wire.failed = "timeout"
    client = wire.client()
    store = client.assignments.setup.journal.records.store

    def handle(req):
        if req.method == "POST":
            records = [json.loads(v.data) for v in store._objects.values()]
            assert len(records) == 1 and records[0]["value"]["phase"] == "sending"
            assert records[0]["value"]["guarantees"]["native_compare_and_set"] is False
        return wire(req)

    shared = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    client.browser_transport._http = shared
    client.existing_transport._http = shared
    with pytest.raises(SakaiError, match="AMBIGUOUS_WRITE_OUTCOME"):
        await client.assignments.create_assignment(principal(), request())
    records = [json.loads(v.data) for v in store._objects.values()]
    assert (
        records[0]["value"]["phase"] == "unknown"
        and records[0]["value"]["ever_unknown"] is True
    )
    assert wire.posts == 1 and len(wire.models) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "portal-user",
        "portal-site",
        "timezone",
        "dst-fold",
        "cross-assignment",
        "changed-zone",
    ],
)
async def test_native_binding_and_timezone_errors_do_not_manufacture_verified_success(
    failure,
):
    import httpx

    wire = SetupHTTP()
    client = wire.client()
    req = request()
    if failure == "timezone":
        wire.zone = "No/SuchZone"
    if failure == "changed-zone":
        wire.readback_zone = "UTC"
    if failure == "dst-fold":
        wire.zone = "America/New_York"
        req = request(
            timezone="America/New_York",
            open_at="2026-11-01T01:30:00-04:00",
            due_at="2026-11-03T12:00:00-05:00",
            close_at="2026-11-03T12:00:00-05:00",
        )

    def handler(r):
        response = wire(r)
        if r.url.path == "/portal/tool/assignments-p":
            data = response.content
            if failure == "portal-user":
                data = data.replace(b'"id": "uid"', b'"id": "foreign"')
            if failure == "portal-site":
                data = data.replace(b'"siteId": "course-a"', b'"siteId": "other"')
            if failure == "cross-assignment" and wire.posts:
                data = data.replace(
                    b"%2Fassignment%2Fa%2Fcourse-a%2F",
                    b"%2Fassignment%2Fa%2Fforeign%2F",
                )
            return httpx.Response(
                200, content=data, headers={"content-type": "text/html"}
            )
        return response

    shared = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client.browser_transport._http = shared
    client.existing_transport._http = shared
    with pytest.raises(SakaiError):
        await client.assignments.create_assignment(principal(), req)
    assert wire.posts == (1 if failure in {"cross-assignment", "changed-zone"} else 0)


@pytest.mark.asyncio
async def test_native_instruction_normalization_returns_known_id_with_explicit_partial_review():
    wire = SetupHTTP()
    wire.failed = "readback"
    result = await wire.client().assignments.create_assignment(principal(), request())
    assert result.assignment_id in wire.models and wire.posts == 1
    assert result.outcome == "partial" and "verify_assignment" in result.remaining_steps
    assert "native_instruction_readback_differs_verify_saved_content" in result.warnings
    assert result.failure.retry_safe is False


@pytest.mark.asyncio
async def test_later_gradebook_outage_preserves_known_saved_assignment():
    import httpx

    wire = SetupHTTP()
    client = wire.client()

    def handler(req):
        if req.url.path == "/api/sites/course-a/grading/item-data" and wire.posts:
            return httpx.Response(503)
        return wire(req)

    shared = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client.existing_transport._http = shared
    client.browser_transport._http = shared
    result = await client.assignments.create_assignment(
        principal(),
        request(
            gradebook={
                "mode": "new_external",
                "category_id": None,
                "release_to_students": True,
                "count_toward_course_grade": True,
            }
        ),
    )
    assert result.assignment_id in wire.models and wire.posts == 1
    assert (
        result.gradebook.status == "unknown"
        and result.gradebook.gradebook_item_id is None
    )
    assert result.outcome == "partial" and result.failure.retry_safe is False


@pytest.mark.asyncio
async def test_uncategorized_counting_policy_conflict_is_rejected_before_write():
    wire = SetupHTTP()
    wire.categories = True
    with pytest.raises(SakaiError, match="UNSUPPORTED_CAPABILITY"):
        await wire.client().assignments.create_assignment(
            principal(),
            request(
                gradebook={
                    "mode": "new_external",
                    "category_id": None,
                    "release_to_students": True,
                    "count_toward_course_grade": True,
                }
            ),
        )
    assert not wire.posts
    context = await wire.client().assignments.get_course_assessment_context(
        principal(), "course-a"
    )
    assert any(
        w.startswith("gradebook_category_choice_metadata_only: ")
        for w in context.warnings
    )


@pytest.mark.asyncio
async def test_inactive_date_defaults_do_not_invalidate_a_publish_revision():
    import json

    wire = SetupHTTP()
    wire.seed()
    client = wire.client()
    context = await client.assignments.get_course_assessment_context(
        principal(), "course-a"
    )
    metadata = json.loads(
        next(
            w.removeprefix("assignment_metadata_only: ")
            for w in context.warnings
            if w.startswith("assignment_metadata_only: ")
        )
    )
    wire.models["assignment-a"].update(
        new_assignment_visible_="2026-10-27T10:00",
        allow_resubmit_close_="2026-10-28T11:00",
        allow_resubmit_number="2",
    )
    result = await client.assignments.publish_assignment(
        principal(),
        PublishAssignmentRequest(
            course_id="course-a",
            assignment_id="assignment-a",
            expected_assignment_revision=metadata["configuration_revision"],
            gradebook={"mode": "none"},
            calendar_deadline="none",
        ),
    )
    assert result.assignment_id == "assignment-a" and wire.posts == 1


@pytest.mark.asyncio
async def test_unverified_numeric_locale_is_rejected_before_write():
    wire = SetupHTTP()
    wire.locale = "de-DE"
    with pytest.raises(SakaiError, match="UNSUPPORTED_CAPABILITY"):
        await wire.client().assignments.create_assignment(principal(), request())
    assert not wire.posts


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"new_assignment_grade_assignment": False},
        {"allowResToggle": True, "allow_resubmit_number": "16"},
    ],
)
async def test_publish_never_treats_inactive_or_unrepresentable_grading_controls_as_points(
    changes,
):
    import json

    wire = SetupHTTP()
    wire.seed(**changes)
    client = wire.client()
    context = await client.assignments.get_course_assessment_context(
        principal(), "course-a"
    )
    row = json.loads(
        next(
            w.removeprefix("assignment_metadata_only: ")
            for w in context.warnings
            if w.startswith("assignment_metadata_only: ")
        )
    )
    with pytest.raises(SakaiError, match="UNSUPPORTED_CAPABILITY"):
        await client.assignments.publish_assignment(
            principal(),
            PublishAssignmentRequest(
                course_id="course-a",
                assignment_id="assignment-a",
                expected_assignment_revision=row["configuration_revision"],
                gradebook={"mode": "none"},
                calendar_deadline="none",
            ),
        )
    assert not wire.posts


@pytest.mark.asyncio
async def test_setup_metadata_and_external_link_verification_never_read_student_scores():
    wire = SetupHTTP()
    wire.functions = ["asn.new", "asn.revise", "gradebook.editAssignments"]
    wire.categories = True
    client = wire.client()
    context = await client.assignments.get_course_assessment_context(
        principal(), "course-a"
    )
    assert context.gradebook.categories[0].id == "5"
    assert context.gradebook.categories[0].weight_percent == 30.0
    assert context.gradebook.categories[0].drop_lowest == 1
    result = await client.assignments.create_assignment(
        principal(),
        request(
            gradebook={
                "mode": "new_external",
                "category_id": "5",
                "release_to_students": True,
                "count_toward_course_grade": True,
            }
        ),
    )
    assert result.gradebook.status == "linked"
    assert not any(
        r.url.path.startswith("/portal/tool/gradebook-p")
        or r.url.path.endswith("/grades")
        or r.url.path.startswith("/direct/assignment")
        for r in wire.calls
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "foreign-site",
        "missing-flag",
        "unknown-category-rule",
        "duplicate",
        "permission",
    ],
)
async def test_context_metadata_authorization_identity_and_unknown_fields_remain_explicit(
    failure,
):
    import httpx

    wire = SetupHTTP()
    wire.categories = True
    client = wire.client()

    def handler(req):
        result = wire(req)
        if req.url.path != "/api/sites/course-a/grading/item-data":
            return result
        if failure == "permission":
            return httpx.Response(403)
        body = result.json()
        if failure == "foreign-site":
            body["items"][0]["context"] = "foreign"
        if failure == "missing-flag":
            body["items"][0].pop("released")
        if failure == "unknown-category-rule":
            body["categories"][0]["dropLowest"] = None
        if failure == "duplicate":
            body["items"].append(body["items"][0])
        return httpx.Response(200, json=body)

    shared = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client.existing_transport._http = shared
    client.browser_transport._http = shared
    if failure in {"foreign-site", "duplicate", "permission"}:
        with pytest.raises(SakaiError):
            await client.assignments.get_course_assessment_context(
                principal(), "course-a"
            )
    else:
        context = await client.assignments.get_course_assessment_context(
            principal(), "course-a"
        )
        assert not context.complete
        if failure == "missing-flag":
            assert context.gradebook.items == [] and any(
                "full_flags_unavailable" in w for w in context.warnings
            )
        else:
            assert context.gradebook.categories == [] and any(
                "full_rules_unavailable" in w for w in context.warnings
            )
    assert not wire.posts


@pytest.mark.asyncio
async def test_publish_does_not_clear_unobserved_javascript_synchronized_tags():
    import json

    wire = SetupHTTP()
    wire.seed()
    wire.form_extras = '<input type="hidden" id="tag_selector" name="tag_selector">'
    client = wire.client()
    context = await client.assignments.get_course_assessment_context(
        principal(), "course-a"
    )
    row = json.loads(
        next(
            w.removeprefix("assignment_metadata_only: ")
            for w in context.warnings
            if w.startswith("assignment_metadata_only: ")
        )
    )
    with pytest.raises(SakaiError, match="UNSUPPORTED_CAPABILITY"):
        await client.assignments.publish_assignment(
            principal(),
            PublishAssignmentRequest(
                course_id="course-a",
                assignment_id="assignment-a",
                expected_assignment_revision=row["configuration_revision"],
                gradebook={"mode": "none"},
                calendar_deadline="none",
            ),
        )
    assert not wire.posts
