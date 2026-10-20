"""Source-derived contracts distinguish observations from native guarantees."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from sakai_mcp.contracts.existing_api import (
    Coverage,
    InstantEncoding,
    Submission,
    collection,
    course_fields,
    decimal_score,
    display_score,
    instant,
    parse,
    student_grade_rows,
    user_permissions,
)
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.cxf import (
    SERVICE,
    SOAP11,
    assignment_list_envelope,
    lean_assignments,
    rpc_return,
    xml,
)

WIRE = json.loads(
    (Path(__file__).parents[2] / "fixtures/existing_http/wire.json").read_text()
)


def test_rich_sites_discard_metadata_and_keep_course_identity_order():
    assert course_fields(WIRE["sites"]) == [
        {"id": "course-a", "title": "Field Methods"},
        {"id": "course-b", "title": "Zoology"},
    ]
    assert course_fields({"sites": []}) == []
    with pytest.raises(SakaiError) as error:
        course_fields({"sites": [{"siteId": "same", "title": "A"}] * 2})
    assert error.value.code == ErrorCode.CONFLICT
    with pytest.raises(SakaiError):
        course_fields({"sites": [{"siteId": "a", "title": "A", "course": "true"}]})


def test_grader_average_is_never_own_score_and_cross_site_never_matches():
    assert student_grade_rows(WIRE["student_grades"], "course-a")[0].score == "0"
    for value, site, expected in [
        (WIRE["grader_grades"], "course-a", ErrorCode.UNSUPPORTED_CAPABILITY),
        (WIRE["student_grades"], "other-course", ErrorCode.CONFLICT),
    ]:
        with pytest.raises(SakaiError) as error:
            student_grade_rows(value, site)
        assert error.value.code == expected


def test_omitted_null_false_and_not_hydrated_are_distinct():
    metadata = parse(Submission, WIRE["submission_metadata"])
    detail = parse(Submission, WIRE["submission_detail"])
    explicit_null = parse(Submission, {"id": "s", "hydrated": True, "returned": None})
    explicit_false = parse(Submission, {"id": "s", "hydrated": True, "returned": False})
    assert metadata.hydrated_flag("returned") is None
    assert detail.hydrated_flag("returned") is False
    assert explicit_null.hydrated_flag("returned") is None
    assert explicit_false.hydrated_flag("returned") is False
    assert "returned" not in detail.model_fields_set
    assert "returned" in explicit_false.model_fields_set
    assert "gradeReleased" not in detail.model_dump()
    assert detail.submittedAttachments[0].contentLength == "20 B"
    assert "synthetic</p>" not in repr(detail)
    with pytest.raises(ValueError):
        detail.hydrated_flag("gradeReleased")


def test_provider_collection_shapes_are_explicit():
    assert len(collection(WIRE["announcement_collection"], "announcement")) == 1
    assert collection([], "assignment") == []
    for value in [
        {"nested": {"assignment_collection": []}},
        "[]",
        None,
        {"other_collection": []},
    ]:
        with pytest.raises(SakaiError):
            collection(value, "assignment")
    with pytest.raises(SakaiError):
        collection([{}, {}], "assignment", max_rows=1)
    with pytest.raises(SakaiError):
        user_permissions(["site.visit", "site.visit"])
    assert user_permissions([]) == frozenset()


@pytest.mark.parametrize(
    "value", ["NaN", "Infinity", "1e3", "1_000", " 1", "1 ", "1,5", 1, True, "-inf"]
)
def test_point_parser_rejects_non_native_numeric_spellings(value):
    with pytest.raises(SakaiError):
        decimal_score(value)


def test_blank_zero_display_and_stored_units_are_distinct():
    assert decimal_score(None) is None and decimal_score("") is None
    assert decimal_score("0") == Decimal(0)
    assert decimal_score("8.50") == Decimal("8.50")
    assert display_score("850", 100) == Decimal("8.5")
    with pytest.raises(SakaiError):
        display_score("8.5", 100)


@pytest.mark.parametrize(
    "value,encoding",
    [
        (1791000000, InstantEncoding.SECONDS),
        (1791000000000, InstantEncoding.MILLISECONDS),
        ("2026-10-03T09:00:00+05:00", InstantEncoding.ISO),
        ("2026-10-03 04:00:00 UTC", InstantEncoding.JAVA_UTC),
    ],
)
def test_explicit_timestamp_units(value, encoding):
    assert instant(value, encoding) == datetime(2026, 10, 3, 4, tzinfo=UTC)


@pytest.mark.parametrize(
    "value,encoding",
    [
        ("2026-10-02T20:00:00", InstantEncoding.ISO),
        ("2026-10-02 20:00:00 PST", InstantEncoding.JAVA_UTC),
        (True, InstantEncoding.SECONDS),
        ("1791000000", InstantEncoding.SECONDS),
        (float("nan"), InstantEncoding.SECONDS),
        ("2026-W40-5T20:00:00Z", InstantEncoding.ISO),
    ],
)
def test_ambiguous_or_malformed_dates_are_not_guessed(value, encoding):
    with pytest.raises(SakaiError):
        instant(value, encoding)


def test_parse_errors_do_not_expose_payload():
    with pytest.raises(SakaiError) as error:
        parse(Submission, {"id": {"private-feedback": "secret"}})
    assert "secret" not in str(error.value) and error.value.__cause__ is None
    assert (
        Coverage(complete=False, reasons=("scope-unverified",), source="A5").evidence
        == "source-derived-unexercised"
    )


def envelope(inner):
    return f'<s:Envelope xmlns:s="{SOAP11}" xmlns:w="{SERVICE}"><s:Body>{inner}</s:Body></s:Envelope>'.encode()


def test_soap_request_has_empty_server_substituted_session_and_escaped_context():
    root = xml(assignment_list_envelope("course-&-a"))
    operation = root.find(f"{{{SOAP11}}}Body")[0]
    assert operation.tag == f"{{{SERVICE}}}getAssignmentsForContext"
    assert operation.find("sessionid").text is None
    assert operation.find("context").text == "course-&-a"


def test_soap_return_then_lean_xml_and_missing_dates():
    result = rpc_return(
        envelope(
            '<w:getAssignmentsForContextResponse><return>&lt;assignments&gt;&lt;assignment id="a" title="Lab" gradeType="3"/&gt;&lt;/assignments&gt;</return></w:getAssignmentsForContextResponse>'
        )
    )
    assignments = lean_assignments(result.encode())
    assert assignments[0].id == "a" and assignments[0].grade_type == 3
    assert assignments[0].due_time is None
    assert lean_assignments(b"<assignments/>") == ()


@pytest.mark.parametrize(
    "data",
    [
        b'<!DOCTYPE x [<!ENTITY a "private">]><assignments>&a;</assignments>',
        b"<assignments/ >",
        b"org.sakaiproject.PermissionException: private",
        b"<x>" * 34 + b"</x>" * 34,
        envelope(
            "<w:getAssignmentsForContextResponse><return>one</return><return>two</return></w:getAssignmentsForContextResponse>"
        ),
        envelope(
            "<w:getAssignmentsForContextResponse><return><nested/></return></w:getAssignmentsForContextResponse>"
        ),
    ],
)
def test_xml_or_soap_errors_are_bounded_and_sanitized(data):
    with pytest.raises(SakaiError):
        if data.startswith(b"<s:Envelope"):
            rpc_return(data)
        else:
            lean_assignments(data)


def test_soap_fault_exception_strings_and_duplicate_ids_never_look_empty():
    with pytest.raises(SakaiError) as error:
        rpc_return(
            envelope(
                "<s:Fault><faultcode>Server</faultcode><faultstring>private</faultstring></s:Fault>"
            )
        )
    assert error.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE
    exception = rpc_return(
        envelope(
            "<w:getAssignmentsForContextResponse><return>java.lang.Exception: private</return></w:getAssignmentsForContextResponse>"
        )
    )
    with pytest.raises(SakaiError):
        lean_assignments(exception.encode())
    with pytest.raises(SakaiError) as error:
        lean_assignments(
            b'<assignments><assignment id="a" title="A" gradeType="3"/><assignment id="a" title="B" gradeType="3"/></assignments>'
        )
    assert error.value.code == ErrorCode.CONFLICT


def test_course_sort_matches_java_utf16_comparison_for_supplementary_characters():
    from sakai_mcp.contracts.existing_api import course_fields

    rows = course_fields(
        {
            "sites": [
                {"siteId": "bmp", "title": "\ue000", "course": True},
                {"siteId": "astral", "title": "\U00010000", "course": True},
            ]
        }
    )
    assert [r["id"] for r in rows] == ["astral", "bmp"]
