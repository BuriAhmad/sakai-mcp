import asyncio

import httpx
import pytest

from sakai_mcp.contracts.grading_native import (
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
    request = GetAssignmentGradingContextRequest(
        course_id="course-a", assignment_id="assignment-a"
    )
    with pytest.raises(SakaiError) as error:
        asyncio.run(client.grading.get_assignment_grading_context(principal(), request))
    assert error.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE


def test_expired_export_maps_to_missing_evidence():
    with pytest.raises(SakaiError) as error:
        SakaiTransport._raise_for_status(410, "GET", unsupported=True)
    assert error.value.code == ErrorCode.NOT_FOUND


def test_context_with_assignment_attachments_stays_unsupported():
    from tests.fixtures.context_http import ContextHTTP

    wire = ContextHTTP()
    wire.raw["attachments"] = ["/content/attachment/opaque/brief.txt"]
    with pytest.raises(SakaiError) as error:
        asyncio.run(
            wire.client().grading.get_assignment_grading_context(
                principal(),
                GetAssignmentGradingContextRequest(
                    course_id="course-a", assignment_id="assignment-a"
                ),
            )
        )
    assert error.value.code == ErrorCode.UNSUPPORTED_CAPABILITY
    assert all("/api/mcp/" not in r.url.path for r in wire.calls)
