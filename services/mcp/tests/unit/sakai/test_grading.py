import asyncio
import json

import httpx
import pytest

from sakai_mcp.contracts.grading_native import (
    GetAssignmentGradesRequest,
    GetAssignmentGradingContextRequest,
    SaveAssignmentGradesRequest,
)
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.client import SakaiClient
from sakai_mcp.sakai.transport import SakaiTransport
from tests.fixtures.authentication import settings
from tests.fixtures.grading_requests import save_request
from tests.fixtures.sakai import FakeOBO, principal


def test_disabled_grading_has_no_network_calls():
    calls = []
    client = SakaiClient(
        settings(),
        FakeOBO(),
        httpx.AsyncClient(transport=httpx.MockTransport(lambda r: calls.append(r))),
    )
    model = GetAssignmentGradingContextRequest(
        course_id="course-a", assignment_id="assignment-a"
    )
    with pytest.raises(SakaiError) as error:
        asyncio.run(client.grading.get_assignment_grading_context(principal(), model))
    assert error.value.code == ErrorCode.UNSUPPORTED_CAPABILITY and not calls


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
    result = asyncio.run(client.grading.save_assignment_grades(principal(), request))
    assert (
        result.outcome == "partial"
        and result.rows[0].stage == "unknown"
        and len(calls) == 1
    )
    calls.clear()
    client = SakaiClient(
        settings(assignment_grading_enabled=True),
        FakeOBO(),
        httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: (calls.append(r), httpx.Response(503))[1]
            )
        ),
    )
    with pytest.raises(SakaiError) as error:
        asyncio.run(client.grading.save_assignment_grades(principal(), request))
    assert error.value.code == ErrorCode.AMBIGUOUS_WRITE_OUTCOME and len(calls) == 1


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
        asyncio.run(client.grading.save_assignment_grades(principal(), request))
    assert error.value.code == ErrorCode.VALIDATION_ERROR
    assert not calls


def test_read_query_failure_is_not_an_ambiguous_write():
    client = SakaiClient(
        settings(assignment_grading_enabled=True),
        FakeOBO(),
        httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503))),
    )
    request = GetAssignmentGradesRequest(
        course_id="course-a",
        assignment_id="assignment-a",
        rows=[{"submission_id": "submission-a", "sakai_user_id": "student-a"}],
    )
    with pytest.raises(SakaiError) as error:
        asyncio.run(client.grading.get_assignment_grades(principal(), request))
    assert error.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE


def test_expired_export_maps_to_missing_evidence():
    with pytest.raises(SakaiError) as error:
        SakaiTransport._raise_for_status(410, "GET", unsupported=True)
    assert error.value.code == ErrorCode.NOT_FOUND
