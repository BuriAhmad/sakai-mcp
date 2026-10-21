"""Actual external capture/proposal defaults; synthetic existing HTTP only."""

import asyncio
import json
from copy import deepcopy
from datetime import UTC, datetime

import pytest

from sakai_mcp.contracts import grading_native as native
from sakai_mcp.contracts.grading_proposals import (
    ProposalPayload,
    ProposalRecord,
    ProposalRow,
)
from sakai_mcp.contracts.submissions import entry
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.serialization import canonical, digest
from sakai_mcp.storage.base import RecordKind, StoredObject
from sakai_mcp.workflows.captures import assignment_revision
from sakai_mcp.workflows.grading import GradingWorkflow
from sakai_mcp.workflows.resources import read_resource, resource_root
from tests.fixtures import grading_data as f
from tests.fixtures.five_tool_http import SUBMISSION, FiveToolHTTP
from tests.fixtures.sakai import principal


async def request(client, export=f.EXPORT):
    _, a, rows = await client.submissions.source(principal(), f.COURSE, f.ASSIGNMENT)
    return native.ExportAssignmentSubmissionsRequest(
        course_id=f.COURSE,
        assignment_id=f.ASSIGNMENT,
        export_request_id=export,
        expected_assignment_revision=assignment_revision(a),
        submissions=[
            native.ExportSelection(
                submission_id=r.id,
                expected_content_revision=entry(r, a).content_revision,
            )
            for r in rows
        ],
    )


async def manifest(client, export=f.EXPORT, **kwargs):
    return await client.grading.get_assignment_submission_export(
        principal(),
        native.GetAssignmentSubmissionExportRequest(
            course_id=f.COURSE, assignment_id=f.ASSIGNMENT, export_id=export, **kwargs
        ),
    )


async def seed_proposal(client):
    # Frozen read fixture; not permission to grade today's incomplete sources.
    c = client.grading.captures
    owner, receipt = await c.manifest(principal(), f.COURSE, f.ASSIGNMENT, f.EXPORT)
    config = f.config()
    rows = [
        ProposalRow(
            submission_id=r.submission_id,
            sakai_user_id=r.sakai_user_ids[0],
            score=None,
            max_score=config.grading.max_points,
            method=None,
            review_status="review_required",
            issues=["source_inventory_incomplete"],
            criteria=[],
            content_revision=r.content_revision,
            grade_revision=None,
            late_status="unknown",
            config_sha256=digest(canonical(config.model_dump())),
            manifest_sha256=digest(canonical(receipt.model_dump())),
            engine_version="sakai-mcq-2",
            engine_sha256="a" * 64,
        )
        for r in receipt.rows
    ]
    payload = ProposalPayload(config=config, rows=rows)
    sha = digest(
        canonical(
            {
                "proposal_id": f.PROPOSAL,
                "export_id": f.EXPORT,
                "payload": payload.model_dump(),
            }
        )
    )
    proposal = ProposalRecord(
        proposal_id=f.PROPOSAL,
        export_id=f.EXPORT,
        request_sha256=sha,
        expires_at=receipt.expires_at,
        payload=payload,
    )
    record = await c.store().create(
        owner,
        RecordKind.PROPOSAL,
        f.PROPOSAL,
        sha,
        {"proposal": proposal.model_dump()},
        expires_at=datetime.fromisoformat(receipt.expires_at),
        now=datetime.now(UTC),
    )
    return owner, record, proposal


@pytest.mark.asyncio
async def test_capture_resource_exact_immutable_bytes_and_no_academic_post():
    w = FiveToolHTTP()
    c = w.client()
    req = await request(c)
    result = await c.grading.export_assignment_submissions(principal(), req)
    assert result.status == "partial"
    page = await manifest(c)
    assert not page.completeness.complete and page.rows[0].status == "incomplete"
    a = page.artifacts[0]
    assert a.sha256 == digest(SUBMISSION["submittedText"].encode())
    uri = (
        resource_root(f.COURSE, f.ASSIGNMENT)
        + f"/exports/{f.EXPORT}/submissions/{f.SUBMISSION}/files/{a.artifact_id}"
    )
    before = list(c.grading.captures.store().store._objects.values())
    w.assignment["submissions"][0]["submittedText"] = "New content"
    data = await read_resource(c, principal(), uri)
    assert (
        data.data == SUBMISSION["submittedText"].encode() and data.mime == "text/html"
    )
    assert await c.grading.export_assignment_submissions(principal(), req) == result
    assert before == list(c.grading.captures.store().store._objects.values())
    assert all(r.method == "GET" for r in w.calls)
    assert "DO NOT EXPOSE" not in page.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        "no-store",
        "permission",
        "group",
        "eid",
        "assignment",
        "content",
        "duplicate",
        "missing",
    ],
)
async def test_capture_preflight_has_no_records_or_legacy(failure):
    w = FiveToolHTTP()
    c = w.client()
    req = await request(c)
    w.calls.clear()
    if failure == "no-store":
        c.grading.captures.records = None
    if failure == "permission":
        w.functions = []
    if failure == "group":
        w.functions = ["asn.grade.groups"]
    if failure == "eid":
        w.native_eid = "wrong"
    if failure == "assignment":
        req.expected_assignment_revision = "old"
    if failure == "content":
        req.submissions[0].expected_content_revision = "old"
    if failure == "duplicate":
        req.submissions.append(req.submissions[0])
    if failure == "missing":
        req.submissions[0].submission_id = "omitted"
    with pytest.raises(SakaiError):
        await c.grading.export_assignment_submissions(principal(), req)
    if failure == "no-store":
        assert not w.calls
    else:
        assert not c.grading.captures.store().store._objects


@pytest.mark.asyncio
async def test_duplicate_payload_conflict_and_attachments_stay_explicitly_incomplete():
    w = FiveToolHTTP()
    w.assignment["submissions"][0]["submittedAttachments"] = [
        {
            "ref": "/content/attachment/course-a/file",
            "name": "answers.txt",
            "type": "text/plain",
            "size": 5,
        }
    ]
    c = w.client()
    req = await request(c)
    await c.grading.export_assignment_submissions(principal(), req)
    page = await manifest(c)
    assert page.rows[0].reasons == [
        "source_inventory_incomplete",
        "attachment_capture_unsupported",
    ]
    with pytest.raises(SakaiError, match="CONFLICT"):
        await c.grading.export_assignment_submissions(
            principal(),
            req.model_copy(update={"expected_assignment_revision": "different"}),
        )
    assert all(a.kind == "inline_text" for a in page.artifacts)


@pytest.mark.asyncio
async def test_changed_during_capture_is_not_ready():
    w = FiveToolHTTP()
    c = w.client()
    req = await request(c)
    store = c.grading.captures.store().store
    original = store.create

    async def change(key, data):
        result = await original(key, data)
        if key.artifact_id:
            w.assignment["submissions"][0]["submittedText"] = "Changed"
        return result

    store.create = change
    await c.grading.export_assignment_submissions(principal(), req)
    page = await manifest(c)
    assert (
        page.rows[0].status == "source_changed"
        and "source_changed" in page.rows[0].reasons
    )


@pytest.mark.asyncio
async def test_two_workers_capture_once_and_pending_never_resumes():
    w = FiveToolHTTP()
    c = w.client()
    req = await request(c)
    other = w.client()
    other.grading.captures.records = c.grading.captures.records
    await asyncio.gather(
        c.grading.export_assignment_submissions(principal(), req),
        other.grading.export_assignment_submissions(principal(), req),
    )
    assert len(c.grading.captures.store().store._objects) == 2
    req2 = req.model_copy(
        update={"export_request_id": "00000000-0000-0000-0000-000000000004"}
    )
    store = c.grading.captures.store().store
    original = store.create

    async def fail(key, data):
        if key.artifact_id:
            raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE)
        return await original(key, data)

    store.create = fail
    with pytest.raises(SakaiError):
        await c.grading.export_assignment_submissions(principal(), req2)
    store.create = original
    before = list(store._objects.values())
    assert (
        await other.grading.export_assignment_submissions(principal(), req2)
    ).status == "pending"
    assert before == list(store._objects.values())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    ["revoked", "removed", "identity", "corrupt-bytes", "corrupt-record", "expired"],
)
async def test_artifact_read_current_scope_expiry_and_integrity(failure):
    w = FiveToolHTTP()
    c = w.client()
    await c.grading.export_assignment_submissions(principal(), await request(c))
    page = await manifest(c)
    aid = page.artifacts[0].artifact_id
    cap = c.grading.captures
    owner, _ = await cap.manifest(principal(), f.COURSE, f.ASSIGNMENT, f.EXPORT)
    store = cap.store().store
    key = cap.store().key(owner, RecordKind.EXPORT, f.EXPORT)
    if failure == "revoked":
        w.functions = []
    if failure == "removed":
        w.assignment["submissions"] = []
    if failure == "identity":
        w.assignment["submissions"][0]["submitters"][0]["id"] = "other"
    if failure == "corrupt-bytes":
        store._objects[
            cap.store().key(owner, RecordKind.EXPORT, f.EXPORT, aid).path()
        ] = StoredObject(b"altered", "test")
    if failure in {"corrupt-record", "expired"}:
        previous = await store.read(key)
        saved = json.loads(previous.data)
        if failure == "corrupt-record":
            saved["value"]["receipt"]["rows"][0]["sakai_user_ids"] = ["other"]
        else:
            saved["expires_at"] = "2000-01-01T00:00:00+00:00"
        await store.replace(key, previous.etag, canonical(saved))
    before = list(store._objects.values())
    with pytest.raises(SakaiError):
        await c.grading.read_grading_artifact(
            principal(), f.COURSE, f.ASSIGNMENT, f.EXPORT, aid
        )
    assert before == list(store._objects.values())


@pytest.mark.asyncio
async def test_manifest_cursor_and_source_changes_do_not_rewrite_history():
    w = FiveToolHTTP()
    w.assignment["submissions"].append({**deepcopy(SUBMISSION), "id": "submission-b"})
    c = w.client()
    await c.grading.export_assignment_submissions(principal(), await request(c))
    first = await manifest(c, limit=1)
    second = await manifest(c, cursor=first.next_cursor, limit=1)
    assert (
        first.next_cursor
        and first.artifacts[0].artifact_id != second.artifacts[0].artifact_id
        and second.next_cursor is None
    )
    with pytest.raises(SakaiError, match="CONFLICT"):
        await manifest(c, cursor="1")


@pytest.mark.asyncio
async def test_frozen_proposal_read_and_reports_never_recompute_or_post():
    w = FiveToolHTTP()
    c = w.client()
    await c.grading.export_assignment_submissions(principal(), await request(c))
    _, _, expected = await seed_proposal(c)
    assert (
        await c.grading.get_proposal(principal(), f.COURSE, f.ASSIGNMENT, f.PROPOSAL)
        == expected
    )
    page = await GradingWorkflow(c).get_proposal(
        principal(), f.COURSE, f.ASSIGNMENT, f.PROPOSAL, None, 50
    )
    assert page.config == expected.payload.config
    uri = (
        resource_root(f.COURSE, f.ASSIGNMENT)
        + f"/proposals/{f.PROPOSAL}/reports/proposals"
    )
    assert (await read_resource(c, principal(), uri)).data == canonical(
        expected.payload.model_dump()
    )
    assert all(r.method == "GET" for r in w.calls)
    w.functions = []
    with pytest.raises(SakaiError):
        await read_resource(c, principal(), uri)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["id", "hash", "expiry", "config", "export"])
async def test_proposal_receipt_integrity_and_source_lifetime(failure):
    w = FiveToolHTTP()
    c = w.client()
    await c.grading.export_assignment_submissions(principal(), await request(c))
    owner, record, _ = await seed_proposal(c)
    value = deepcopy(record.value)
    proposal = value["value"]["proposal"]
    if failure == "id":
        proposal["proposal_id"] = f.EXPORT
    if failure == "hash":
        proposal["request_sha256"] = "a" * 64
    if failure == "expiry":
        value["expires_at"] = "2000-01-01T00:00:00+00:00"
    if failure == "config":
        proposal["payload"]["config"]["course_id"] = "foreign"
    if failure == "export":
        proposal["export_id"] = "00000000-0000-0000-0000-000000000009"
        proposal["request_sha256"] = value["payload_hash"] = digest(
            canonical(
                {
                    "proposal_id": f.PROPOSAL,
                    "export_id": proposal["export_id"],
                    "payload": proposal["payload"],
                }
            )
        )
    cap = c.grading.captures
    await cap.store().store.replace(
        cap.store().key(owner, RecordKind.PROPOSAL, f.PROPOSAL),
        record.etag,
        canonical(value),
    )
    with pytest.raises(SakaiError):
        await c.grading.get_proposal(principal(), f.COURSE, f.ASSIGNMENT, f.PROPOSAL)


def test_no_proposal_creation_or_assessment_api_remains():
    from sakai_mcp.sakai.grading import GradingOperations
    from sakai_mcp.workflows.captures import Captures

    assert not hasattr(GradingWorkflow, "prepare_mcq")
    assert not hasattr(GradingOperations, "create_proposal")
    assert not hasattr(Captures, "create_proposal")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "suffix",
    [
        "/exports/id/not-a-manifest",
        "/exports/id/submissions/s/not-files/f",
        "/proposals/id/reports/unknown",
    ],
)
async def test_invalid_resource_grammar_has_no_remote_effect(suffix):
    w = FiveToolHTTP()
    c = w.client()
    with pytest.raises(SakaiError):
        await read_resource(
            c, principal(), resource_root(f.COURSE, f.ASSIGNMENT) + suffix
        )
    assert not w.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["tenant_id", "object_id"])
async def test_same_native_uid_different_delegated_owner_cannot_read_capture(field):
    from dataclasses import replace

    from tests.fixtures.sakai import FakeOBO

    w = FiveToolHTTP()
    c = w.client()
    await c.grading.export_assignment_submissions(principal(), await request(c))

    class DifferentOwner(FakeOBO):
        async def acquire(self, token):
            return replace(await super().acquire(token), **{field: "other-owner"})

    for transport in [c.existing_transport, c.browser_transport]:
        transport.obo = DifferentOwner()
    with pytest.raises(SakaiError, match="NOT_FOUND"):
        await manifest(c)


@pytest.mark.asyncio
async def test_expired_request_id_never_recaptures_or_extends_expiry():
    w = FiveToolHTTP()
    c = w.client()
    req = await request(c)
    await c.grading.export_assignment_submissions(principal(), req)
    cap = c.grading.captures
    owner, _ = await cap.manifest(principal(), f.COURSE, f.ASSIGNMENT, f.EXPORT)
    key = cap.store().key(owner, RecordKind.EXPORT, f.EXPORT)
    old = await cap.store().store.read(key)
    value = json.loads(old.data)
    value["expires_at"] = "2000-01-01T00:00:00+00:00"
    await cap.store().store.replace(key, old.etag, canonical(value))
    before = list(cap.store().store._objects.values())
    with pytest.raises(SakaiError, match="NOT_FOUND"):
        await c.grading.export_assignment_submissions(principal(), req)
    assert before == list(cap.store().store._objects.values())


@pytest.mark.asyncio
async def test_disabled_capture_defaults_fail_before_http():
    w = FiveToolHTTP()
    c = w.client()
    req = await request(c)
    c.grading.settings = c.grading.settings.model_copy(
        update={"assignment_grading_enabled": False}
    )
    w.calls.clear()
    for operation in [
        lambda: c.grading.export_assignment_submissions(principal(), req),
        lambda: manifest(c),
        lambda: c.grading.get_proposal(principal(), f.COURSE, f.ASSIGNMENT, f.PROPOSAL),
    ]:
        with pytest.raises(SakaiError, match="UNSUPPORTED_CAPABILITY"):
            await operation()
    assert not w.calls


@pytest.mark.asyncio
async def test_proposal_pagination_preserves_public_numeric_cursor_grammar():
    wire = FiveToolHTTP()
    other = deepcopy(SUBMISSION)
    other.update(id="submission-b", submitters=[{"id": "student-b"}])
    wire.assignment["submissions"].append(other)
    client = wire.client()
    await client.grading.export_assignment_submissions(
        principal(), await request(client)
    )
    await seed_proposal(client)
    workflow = GradingWorkflow(client)
    first = await workflow.get_proposal(
        principal(), f.COURSE, f.ASSIGNMENT, f.PROPOSAL, None, 1
    )
    assert first.next_cursor == "1" and first.rows[0].score is None
    second = await workflow.get_proposal(
        principal(), f.COURSE, f.ASSIGNMENT, f.PROPOSAL, first.next_cursor, 1
    )
    assert second.next_cursor is None and second.total == 2
    assert second.rows[0].submission_id != first.rows[0].submission_id
    for cursor in ["-1", "http1-stale:1", "10000000", "3"]:
        with pytest.raises(SakaiError):
            await workflow.get_proposal(
                principal(), f.COURSE, f.ASSIGNMENT, f.PROPOSAL, cursor, 1
            )
