"""Actual default receipt routing and one-send transitional grading commits."""

from copy import deepcopy

import httpx
import pytest

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.serialization import canonical
from sakai_mcp.sakai.client import SakaiClient
from sakai_mcp.storage.base import StoredObject
from sakai_mcp.storage.memory import MemoryObjectStore
from sakai_mcp.storage.records import PrivateRecords
from tests.fixtures.authentication import settings
from tests.fixtures.five_tool_http import FiveToolHTTP
from tests.fixtures.grading_operations import receipt
from tests.fixtures.grading_requests import save_request
from tests.fixtures.sakai import FakeOBO, principal


def fixture():
    wire = FiveToolHTTP()
    store = MemoryObjectStore()
    req = native.SaveAssignmentGradesRequest.model_validate(save_request())
    posts = []
    response = receipt(req)

    client = SakaiClient(
        settings(assignment_grading_enabled=True),
        FakeOBO(),
        httpx.AsyncClient(transport=httpx.MockTransport(wire)),
        private_records=PrivateRecords(store),
    )
    from types import SimpleNamespace

    # Journal component seam: no legacy HTTP endpoint or business sender.
    async def synthetic_send(request):
        posts.append(request)
        return response

    async def journal_sender(principal, request, kind):
        return await client.grading.operations.commit(
            principal, request, kind, lambda: client.grading.writes.send(request)
        )

    client.grading.writes = SimpleNamespace(execute=journal_sender, send=synthetic_send)
    return wire, store, client, req, posts, response


def read_request(req):
    return native.GetAssignmentGradingOperationRequest(
        course_id=req.course_id,
        assignment_id=req.assignment_id,
        operation_id=req.operation_id,
    )


@pytest.mark.asyncio
async def test_confirmed_partial_is_external_and_repeat_never_sends():
    w, store, c, req, posts, expected = fixture()
    result = await c.grading.save_assignment_grades(principal(), req)
    assert result == expected and len(posts) == 1
    objects = deepcopy(store._objects)
    w.calls.clear()
    for _ in range(2):
        read = await c.grading.get_assignment_grading_operation(
            principal(), read_request(req)
        )
        assert read.outcome == "partial" and read.rows[0].stage == "unknown"
        assert read.rows[0].gradebook_score is None
        assert "historical_gradebook_values_withheld" in read.warnings
    repeated = await c.grading.save_assignment_grades(principal(), req)
    assert repeated == read and len(posts) == 1 and objects == store._objects
    assert all(r.method == "GET" and "/api/mcp/" not in r.url.path for r in w.calls)


@pytest.mark.asyncio
async def test_lost_reply_has_durable_unknown_and_no_replay():
    _w, store, c, req, posts, _ = fixture()

    async def lost(*args, **kwargs):
        # Sending is already persisted before the native request is attempted.
        assert next(iter(store._objects.values())).data.find(b'"phase":"sending"') > 0
        posts.append("lost")
        raise SakaiError(ErrorCode.AMBIGUOUS_WRITE_OUTCOME)

    c.grading.writes.send = lost
    with pytest.raises(SakaiError, match="AMBIGUOUS_WRITE_OUTCOME"):
        await c.grading.save_assignment_grades(principal(), req)
    read = await c.grading.get_assignment_grading_operation(
        principal(), read_request(req)
    )
    assert read.outcome == "unknown" and read.rows[0].grade_released is None
    assert read.rows[0].content_revision is None
    assert await c.grading.save_assignment_grades(principal(), req) == read
    assert len(posts) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    ["no-store", "permission", "identity", "target", "corrupt", "hash", "missing"],
)
async def test_receipt_failures_never_read_legacy_or_write(failure):
    w, store, c, req, posts, _ = fixture()
    await c.grading.save_assignment_grades(principal(), req)
    posts.clear()
    w.calls.clear()
    if failure == "no-store":
        c.grading.operations.records = None
    elif failure == "permission":
        w.functions = ["asn.grade.groups"]
    elif failure == "identity":
        w.native_eid = "different"
    elif failure == "target":
        w.assignment["submissions"][0]["submitters"][0]["id"] = "another-student"
    elif failure in {"corrupt", "hash"}:
        key, obj = next(iter(store._objects.items()))
        import json

        value = json.loads(obj.data)
        if failure == "corrupt":
            value["value"]["receipt"]["rows"][0]["sakai_user_id"] = "another"
        else:
            value["payload_hash"] = "a" * 64
        store._objects[key] = StoredObject(canonical(value), obj.etag)
    elif failure == "missing":
        store._objects.clear()
    with pytest.raises(SakaiError):
        await c.grading.get_assignment_grading_operation(principal(), read_request(req))
    assert not posts
    if failure == "no-store":
        assert not w.calls


@pytest.mark.asyncio
async def test_request_id_collision_and_persistence_failure_never_send():
    _w, store, c, req, posts, _ = fixture()
    await c.grading.save_assignment_grades(principal(), req)
    other = native.SaveAssignmentGradesRequest.model_validate(save_request("5"))
    with pytest.raises(SakaiError, match="CONFLICT"):
        await c.grading.save_assignment_grades(principal(), other)
    assert len(posts) == 1
    req.operation_id = "00000000-0000-0000-0000-000000000002"

    async def unavailable(*args, **kwargs):
        raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE)

    store.replace = unavailable
    with pytest.raises(SakaiError, match="DEPENDENCY_UNAVAILABLE"):
        await c.grading.save_assignment_grades(principal(), req)
    assert len(posts) == 1
    # A prepared intent does not resume even when explicitly called again.
    result = await c.grading.save_assignment_grades(principal(), req)
    assert result.outcome == "unknown" and len(posts) == 1


@pytest.mark.asyncio
async def test_two_workers_only_send_once_and_receipt_reply_failure_stays_unknown():
    import asyncio

    _, store, c, req, posts, response = fixture()
    await asyncio.gather(
        *[c.grading.save_assignment_grades(principal(), req) for _ in range(2)]
    )
    assert len(posts) == 1
    req.operation_id = "00000000-0000-0000-0000-000000000002"
    response.operation_id = req.operation_id
    original = store.replace
    calls = 0

    async def fail_final(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE)
        return await original(*args, **kwargs)

    store.replace = fail_final
    with pytest.raises(SakaiError, match="AMBIGUOUS_WRITE_OUTCOME"):
        await c.grading.save_assignment_grades(principal(), req)
    read = await c.grading.get_assignment_grading_operation(
        principal(), read_request(req)
    )
    assert read.outcome == "unknown" and len(posts) == 2


@pytest.mark.asyncio
async def test_release_uses_same_journal_and_no_store_commit_has_no_http():
    from sakai_mcp.grading.serialization import payload_hash

    w, _, c, req, posts, response = fixture()
    rows = [
        {
            "submission_id": "submission-a",
            "sakai_user_id": "student-a",
            "expected_content_revision": "content",
            "expected_grade_revision": "grade",
            "expected_score": "4",
            "expected_feedback_sha256": None,
        }
    ]
    release = native.ReleaseAssignmentGradesRequest.model_validate(
        {
            **req.model_dump(),
            "grades": rows,
            "payload_sha256": payload_hash(
                "release",
                req.course_id,
                req.assignment_id,
                req.expected_assignment_revision,
                rows,
            ),
        }
    )
    response.kind = "release"
    response.payload_sha256 = release.payload_sha256
    await c.grading.release_assignment_grades(principal(), release)
    assert len(posts) == 1
    assert (
        await c.grading.get_assignment_grading_operation(principal(), read_request(req))
    ).kind == "release"
    c.grading.operations.records = None
    w.calls.clear()
    posts.clear()
    with pytest.raises(SakaiError, match="DEPENDENCY_UNAVAILABLE"):
        await c.grading.save_assignment_grades(principal(), req)
    assert not w.calls and not posts


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure", ["expired", "owner", "provenance", "warning-budget"]
)
async def test_record_binding_expiry_and_warning_contract_fail_closed(failure):
    import json

    from sakai_mcp.grading.serialization import digest

    _, store, c, req, posts, _ = fixture()
    await c.grading.save_assignment_grades(principal(), req)
    key, obj = next(iter(store._objects.items()))
    value = json.loads(obj.data)
    if failure == "expired":
        value["expires_at"] = "2000-01-01T00:00:00+00:00"
    elif failure == "owner":
        value["owner"] = "a" * 64
    elif failure == "provenance":
        value["value"]["provenance"] = "other-workflow"
    else:
        value["value"]["receipt"]["warnings"] = [
            f"native_warning_{i}" for i in range(30)
        ]
        value["value"]["receipt_sha256"] = digest(canonical(value["value"]["receipt"]))
    store._objects[key] = StoredObject(canonical(value), obj.etag)
    with pytest.raises(SakaiError):
        await c.grading.get_assignment_grading_operation(principal(), read_request(req))
    assert len(posts) == 1
