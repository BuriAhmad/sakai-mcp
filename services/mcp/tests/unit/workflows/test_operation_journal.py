"""Uncertain-send receipts cannot become replay authorization or causal proof."""

import asyncio
from datetime import UTC, datetime

import pytest

from sakai_mcp.errors import SakaiError
from sakai_mcp.grading.serialization import canonical, digest
from sakai_mcp.storage.base import RecordKind, RecordOwner
from sakai_mcp.storage.memory import MemoryObjectStore
from sakai_mcp.storage.records import PrivateRecords
from sakai_mcp.workflows.operation_journal import OperationJournal

OWNER = RecordOwner("tenant", "actor", "uid", "course", "assignment")
ID = "11111111-1111-4111-8111-111111111111"
NOW = datetime(2026, 10, 18, tzinfo=UTC)
REQUEST = {"kind": "synthetic-save", "rows": [{"id": "synthetic-row", "score": "8.5"}]}
HASH = digest(canonical(REQUEST))


@pytest.mark.asyncio
async def test_concurrent_workers_only_one_obtains_a_send_intent():
    journal = OperationJournal(PrivateRecords(MemoryObjectStore()))
    await journal.prepare(OWNER, ID, REQUEST, HASH, now=NOW)
    outcomes = await asyncio.gather(
        journal.begin_send(OWNER, ID, HASH, now=NOW),
        journal.begin_send(OWNER, ID, HASH, now=NOW),
        return_exceptions=True,
    )
    assert sum(isinstance(v, SakaiError) for v in outcomes) == 1
    assert (await journal.read(OWNER, ID, now=NOW)).value["value"]["phase"] == "sending"
    with pytest.raises(SakaiError):
        await journal.begin_send(OWNER, ID, HASH, now=NOW)


@pytest.mark.asyncio
async def test_unknown_then_matching_readback_preserves_attribution_uncertainty():
    records = PrivateRecords(MemoryObjectStore())
    journal = OperationJournal(records)
    await journal.prepare(OWNER, ID, REQUEST, HASH, now=NOW)
    await journal.begin_send(OWNER, ID, HASH, now=NOW)
    await journal.unknown(OWNER, ID, now=NOW)
    result = await journal.observe(
        OWNER,
        ID,
        {"assignment_matches": True, "gradebook_verified": None},
        partial=True,
        now=NOW,
    )
    value = result.value["value"]
    assert value["phase"] == "partial" and value["ever_unknown"]
    assert value["attribution"] == "uncertain"
    assert value["guarantees"] == {
        "native_compare_and_set": False,
        "atomic_batch": False,
        "readback_proves_causation": False,
    }
    repeated = await journal.prepare(OWNER, ID, REQUEST, HASH, now=NOW)
    assert repeated.value["value"]["phase"] == "partial"
    with pytest.raises(SakaiError):
        await journal.begin_send(OWNER, ID, HASH, now=NOW)
    assert (
        len((await journal.read(OWNER, ID, now=NOW)).value["value"]["observations"])
        == 2
    )


@pytest.mark.asyncio
async def test_unapproved_or_legacy_payload_cannot_be_sent():
    records = PrivateRecords(MemoryObjectStore())
    journal = OperationJournal(records)
    with pytest.raises(SakaiError):
        await journal.prepare(OWNER, ID, REQUEST, "b" * 64, now=NOW)
    await records.create(
        OWNER,
        RecordKind.OPERATION,
        ID,
        HASH,
        {"phase": "prepared", "provenance": "legacy-native-v1"},
        expires_at=None,
        now=NOW,
    )
    with pytest.raises(SakaiError):
        await journal.begin_send(OWNER, ID, HASH, now=NOW)


@pytest.mark.asyncio
async def test_read_and_observe_before_send_cannot_initiate_native_work():
    journal = OperationJournal(PrivateRecords(MemoryObjectStore()))
    await journal.prepare(OWNER, ID, REQUEST, HASH, now=NOW)
    assert (await journal.read(OWNER, ID, now=NOW)).value["value"][
        "phase"
    ] == "prepared"
    with pytest.raises(SakaiError):
        await journal.observe(OWNER, ID, {"matches": True}, partial=False, now=NOW)
