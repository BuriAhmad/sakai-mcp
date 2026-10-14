import asyncio
import hashlib
import json

import httpx
import pytest
from pydantic import ValidationError

from sakai_mcp.auth import EntraTokenVerifier
from sakai_mcp.grading_evaluator import evaluate_mcq, payload_hash, report_csv
from sakai_mcp.grading_models import (
    CONTRACTS,
    FeedbackPatch,
    SaveAssignmentGradesRequest,
)
from sakai_mcp.sakai_client import ErrorCode, SakaiClient, SakaiError
from sakai_mcp.server import create_server
from tests.helpers import settings
from tests.protocol.test_server import FakeClient
from tests.unit.test_sakai_client import FakeOBO, principal


@pytest.mark.parametrize(
    "setup,grading,count",
    [(False, False, 5), (True, False, 8), (False, True, 19), (True, True, 22)],
)
def test_independent_catalog_gates(setup, grading, count):
    config = settings(
        assignment_setup_enabled=setup, assignment_grading_enabled=grading
    )
    server = create_server(
        config, FakeClient(), EntraTokenVerifier(config, lambda _: None)
    )
    catalog = asyncio.run(server.list_tools())
    assert len(catalog) == count
    assert (set(CONTRACTS) <= {t.name for t in catalog}) == grading
    if grading:
        save = next(t for t in catalog if t.name == "save_assignment_grades")
        assert (
            save.annotations.read_only_hint is False
            and save.annotations.idempotent_hint is False
        )
        assert "expected_grade_revision" in str(save.input_schema)
        assert "invoke" not in save.input_schema["properties"]


def test_disabled_grading_has_no_network_calls():
    calls = []
    client = SakaiClient(
        settings(),
        FakeOBO(),
        httpx.AsyncClient(transport=httpx.MockTransport(lambda r: calls.append(r))),
    )
    model = CONTRACTS["get_assignment_grading_context"][0](
        course_id="course-a", assignment_id="assignment-a"
    )
    with pytest.raises(SakaiError) as error:
        asyncio.run(
            client.grading_request("get_assignment_grading_context", principal(), model)
        )
    assert error.value.code == ErrorCode.UNSUPPORTED_CAPABILITY and not calls


def save_request(score="4"):
    grades = [
        {
            "submission_id": "submission-a",
            "sakai_user_id": "student-a",
            "expected_content_revision": "content",
            "expected_grade_revision": "grade",
            "score": score,
            "feedback": {"action": "preserve", "text": None},
        }
    ]
    return {
        "course_id": "course-a",
        "assignment_id": "assignment-a",
        "operation_id": "00000000-0000-0000-0000-000000000001",
        "mode": "commit",
        "expected_assignment_revision": "config",
        "payload_sha256": payload_hash(
            "save", "course-a", "assignment-a", "config", grades
        ),
        "grades": grades,
    }


@pytest.mark.parametrize("score", [True, 4, 4.5, "NaN", "Infinity", "-1", "04"])
def test_scores_are_strict_exact_decimal_strings(score):
    with pytest.raises(ValidationError):
        SaveAssignmentGradesRequest.model_validate(save_request(score))


@pytest.mark.parametrize(
    "action,text",
    [("preserve", "overwrite"), ("clear", "overwrite"), ("replace", None)],
)
def test_feedback_patch_does_not_clear_omitted_fields(action, text):
    with pytest.raises(ValidationError):
        FeedbackPatch(action=action, text=text)


def test_partial_receipt_preserves_rows_and_post_is_not_replayed():
    calls = []
    request = SaveAssignmentGradesRequest.model_validate(save_request())
    receipt = {
        "operation_id": request.operation_id,
        "kind": "save",
        "mode": "commit",
        "payload_sha256": request.payload_sha256,
        "outcome": "partial",
        "observed_at": "2026-10-09T00:00:00Z",
        "warnings": ["manual_reconciliation_required"],
        "rows": [
            {
                "submission_id": "submission-a",
                "sakai_user_id": "student-a",
                "stage": "unknown",
                "content_revision": "content",
                "grade_revision": "grade",
                "assignment_score": None,
                "grade_released": False,
                "returned": False,
                "gradebook_score": None,
                "reason": "commit_in_progress",
                "retry_action": "human_reconciliation",
            }
        ],
    }

    def handler(r):
        calls.append(r)
        assert r.headers["authorization"] == "Bearer synthetic-token"
        assert r.url.path.endswith("/course-a/assignments/assignment-a/grading-save")
        assert "course_id" not in json.loads(r.content)
        return httpx.Response(200, json=receipt)

    client = SakaiClient(
        settings(assignment_grading_enabled=True),
        FakeOBO(),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = asyncio.run(
        client.grading_request("save_assignment_grades", principal(), request)
    )
    assert (
        result.outcome == "partial"
        and result.rows[0].stage == "unknown"
        and len(calls) == 1
    )
    calls.clear()
    client._http = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: (calls.append(r), httpx.Response(503))[1]
        )
    )
    with pytest.raises(SakaiError) as error:
        asyncio.run(
            client.grading_request("save_assignment_grades", principal(), request)
        )
    assert error.value.code == ErrorCode.AMBIGUOUS_WRITE_OUTCOME and len(calls) == 1


def test_grading_tool_invocation_validates_and_forwards(monkeypatch):
    import sakai_mcp.grading_tools as tools

    monkeypatch.setattr(tools, "get_access_token", principal)

    class Client(FakeClient):
        async def grading_request(self, name, token, request):
            assert name == "list_assignment_submissions" and request.limit == 50
            return {
                "items": [],
                "next_cursor": None,
                "snapshot_revision": "snapshot",
                "observed_at": "2026-10-09T00:00:00Z",
                "completeness": {"complete": True, "scope": "site", "reasons": []},
                "warnings": [],
            }

    config = settings(assignment_grading_enabled=True)
    server = create_server(config, Client(), EntraTokenVerifier(config, lambda _: None))
    result = asyncio.run(
        server.call_tool(
            "list_assignment_submissions",
            {"course_id": "course-a", "assignment_id": "assignment-a"},
        )
    )
    assert result.is_error is not True


def make_evidence(data: bytes, name="roll.txt"):
    manifest = {
        "course_id": "course-a",
        "assignment_id": "assignment-a",
        "rows": [
            {
                "submission_id": "submission-a",
                "sakai_user_ids": ["student-a"],
                "status": "ready",
                "content_revision": "content",
                "artifact_ids": ["artifact"],
            }
        ],
        "artifacts": [
            {
                "artifact_id": "artifact",
                "original_name": name,
                "submission_id": "submission-a",
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        ],
    }
    config = {
        "course_id": "course-a",
        "assignment_id": "assignment-a",
        "assignment_revision": "config",
        "submission_contract": {
            "file_count": 1,
            "encoding": "utf-8",
            "alphabet": ["A", "B", "C", "D"],
            "answer_count": 5,
            "filename": "<roll-number>.txt",
        },
        "expected_filenames": {"student-a": "roll.txt"},
        "normalization": {
            "uppercase_answers": True,
            "trim_answer_whitespace": True,
            "extension_case": True,
        },
        "grading": {
            "method": "deterministic_mcq",
            "key": ["A", "C", "B", "D", "A"],
            "max_points": "5",
            "per_correct": "1",
            "per_incorrect": "0",
            "negative_marking": False,
        },
        "policies": {"late_penalty": None},
        "identity": {"filename_mismatch": "review_required"},
    }
    context = {
        "assignment": {"configuration_revision": "config", "max_points": "5"},
        "completeness": {"complete": True},
        "supported": {"prepare": True},
    }
    roster = [
        {
            "submission_id": "submission-a",
            "content_revision": "content",
            "grade_revision": "grade",
            "late_status": "on_time",
            "submitters": [{"sakai_user_id": "student-a"}],
            "status": "submitted",
        }
    ]
    return config, context, roster, manifest, {"artifact": data}


@pytest.mark.parametrize(
    "data,score",
    [
        (b"A\nC\nB\nD\nA\n", "5"),
        (b"A\nC\nA\nD\nA\n", "4"),
        (b"a\nc\nb\nd\na\n", "5"),
        (b" A \n C\nB \nD\nA\n", "5"),
        (b"A\nC\nB\nD\n", None),
        (b"A\nC\nX\nD\nA\n", None),
        (b"", None),
        (b"%PDF-1.7 fake", None),
        (b"\n" * 500_000, None),
    ],
)
def test_deterministic_known_cases_preserve_raw(data, score):
    config, context, roster, manifest, files = make_evidence(data)
    result = evaluate_mcq(config, context, roster, manifest, files)
    assert result[0]["score"] == score
    assert result[0]["review_status"] == (
        "proposed" if score is not None else "review_required"
    )
    assert files["artifact"] == data
    assert "submission_id" in report_csv(result)


def test_integrity_failure_and_changed_identity_are_rejected():
    config, context, roster, manifest, files = make_evidence(b"A\nC\nB\nD\nA\n")
    files["artifact"] = b"changed"
    with pytest.raises(ValueError, match="integrity"):
        evaluate_mcq(config, context, roster, manifest, files)
    roster[0]["submitters"] = [{"sakai_user_id": "wrong"}]
    result = evaluate_mcq(config, context, roster, manifest, files)
    assert (
        result[0]["score"] is None and "source_identity_changed" in result[0]["issues"]
    )


def test_oversized_feedback_is_rejected_before_network():
    calls = []
    client = SakaiClient(
        settings(assignment_grading_enabled=True),
        FakeOBO(),
        httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: calls.append(request) or httpx.Response(200, json={})
            )
        ),
    )
    value = save_request()
    value["grades"][0]["feedback"] = {"action": "replace", "text": "x" * 61_000}
    request = SaveAssignmentGradesRequest.model_validate(value)
    with pytest.raises(SakaiError) as error:
        asyncio.run(
            client.grading_request("save_assignment_grades", principal(), request)
        )
    assert error.value.code == ErrorCode.VALIDATION_ERROR
    assert not calls


def test_read_query_failure_is_not_an_ambiguous_write():
    client = SakaiClient(
        settings(assignment_grading_enabled=True),
        FakeOBO(),
        httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503))),
    )
    request = CONTRACTS["get_assignment_grades"][0](
        course_id="course-a",
        assignment_id="assignment-a",
        rows=[{"submission_id": "submission-a", "sakai_user_id": "student-a"}],
    )
    with pytest.raises(SakaiError) as error:
        asyncio.run(
            client.grading_request("get_assignment_grades", principal(), request)
        )
    assert error.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE


def test_expired_export_maps_to_missing_evidence():
    with pytest.raises(SakaiError) as error:
        SakaiClient._raise_for_status(410, "GET", unsupported=True)
    assert error.value.code == ErrorCode.NOT_FOUND
