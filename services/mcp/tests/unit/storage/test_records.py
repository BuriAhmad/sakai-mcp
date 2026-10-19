"""Conditional storage privacy, idempotency, immutability, expiry and lease races."""

import asyncio
import hashlib
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.storage.base import ObjectKey, RecordKind, RecordOwner
from sakai_mcp.storage.memory import MemoryObjectStore
from sakai_mcp.storage.records import PrivateRecords

OWNER = RecordOwner("tenant-a", "actor-a", "uid-a", "course-a", "assignment-a")
ID = "11111111-1111-4111-8111-111111111111"
ARTIFACT = "22222222-2222-4222-8222-222222222222"
HASH = "a" * 64
NOW = datetime(2026, 10, 18, tzinfo=UTC)


def key(owner=OWNER):
    return ObjectKey(owner.namespace(), RecordKind.OPERATION, ID)


@pytest.mark.asyncio
async def test_two_writers_cannot_create_or_replace_same_revision():
    store = MemoryObjectStore()
    outcomes = await asyncio.gather(
        store.create(key(), b"one"), store.create(key(), b"two"), return_exceptions=True
    )
    assert sum(isinstance(v, SakaiError) for v in outcomes) == 1
    first = await store.read(key())
    outcomes = await asyncio.gather(
        store.replace(key(), first.etag, b"three"),
        store.replace(key(), first.etag, b"four"),
        return_exceptions=True,
    )
    assert sum(isinstance(v, SakaiError) for v in outcomes) == 1
    assert (await store.read(key())).etag != first.etag


@pytest.mark.asyncio
async def test_owners_are_separate_and_paths_are_not_caller_supplied():
    store = MemoryObjectStore()
    await store.create(key(), b"private")
    for owner in [
        replace(OWNER, tenant="tenant-b"),
        replace(OWNER, object_id="actor-b"),
        replace(OWNER, sakai_uid="uid-b"),
        replace(OWNER, course="course-b"),
        replace(OWNER, assignment="assignment-b"),
    ]:
        with pytest.raises(SakaiError) as error:
            await store.read(key(owner))
        assert error.value.code == ErrorCode.NOT_FOUND
    for bad in [
        replace(key(), record_id="../../private"),
        replace(key(), artifact_id="../file"),
        replace(key(), namespace="user-selected-folder"),
    ]:
        with pytest.raises(SakaiError):
            await store.read(bad)
    assert "uid-a" not in key().path() and "uid-a" not in repr(OWNER)


@pytest.mark.asyncio
async def test_repeated_request_uses_frozen_record_and_original_expiry():
    store = MemoryObjectStore()
    records = PrivateRecords(store)
    first = await records.create(
        OWNER,
        RecordKind.EXPORT,
        ID,
        HASH,
        {"state": "ready", "source": "original"},
        expires_at=NOW + timedelta(hours=1),
        now=NOW,
    )
    repeated = await records.create(
        OWNER,
        RecordKind.EXPORT,
        ID,
        HASH,
        {"state": "ready", "source": "newer"},
        expires_at=NOW + timedelta(hours=2),
        now=NOW,
    )
    assert first == repeated and repeated.value["value"]["source"] == "original"
    with pytest.raises(SakaiError) as conflict:
        await records.create(
            OWNER,
            RecordKind.EXPORT,
            ID,
            "b" * 64,
            {},
            expires_at=NOW + timedelta(hours=1),
            now=NOW,
        )
    assert conflict.value.code == ErrorCode.CONFLICT
    with pytest.raises(SakaiError) as expired:
        await records.read(OWNER, RecordKind.EXPORT, ID, now=NOW + timedelta(hours=1))
    assert expired.value.code == ErrorCode.NOT_FOUND
    assert (
        await store.read(records.key(OWNER, RecordKind.EXPORT, ID))
    ).data  # Delayed physical deletion doesn't grant access.


@pytest.mark.asyncio
async def test_artifacts_are_immutable_hash_checked_and_denied_after_source_expiry():
    store = MemoryObjectStore()
    records = PrivateRecords(store)
    await records.create(
        OWNER,
        RecordKind.EXPORT,
        ID,
        HASH,
        {"state": "ready"},
        expires_at=NOW + timedelta(hours=1),
        now=NOW,
    )
    artifact = records.key(OWNER, RecordKind.EXPORT, ID, ARTIFACT)
    original = await store.create(artifact, b"synthetic bytes")
    digest = hashlib.sha256(original.data).hexdigest()
    assert (
        await records.artifact(
            OWNER, ID, ARTIFACT, expected_size=15, expected_sha256=digest, now=NOW
        )
        == original.data
    )
    with pytest.raises(SakaiError):
        await store.replace(artifact, original.etag, b"changed")
    with pytest.raises(SakaiError):
        await records.artifact(
            OWNER, ID, ARTIFACT, expected_size=15, expected_sha256="b" * 64, now=NOW
        )
    with pytest.raises(SakaiError):
        await records.artifact(
            OWNER,
            ID,
            ARTIFACT,
            expected_size=15,
            expected_sha256=digest,
            now=NOW + timedelta(hours=1),
        )


@pytest.mark.asyncio
async def test_lease_expiry_and_stale_release_do_not_unlock_a_new_writer():
    clock = [0.0]
    store = MemoryObjectStore(lambda: clock[0])
    first = await store.create(key(), b"prepared")
    async with store.lease(key()) as old:
        with pytest.raises(SakaiError):
            await store.replace(key(), first.etag, b"without-lease")
        with pytest.raises(SakaiError):
            async with store.lease(key()):
                pytest.fail("lease overlap")
        clock[0] = 31
        async with store.lease(key()) as current:
            with pytest.raises(SakaiError):
                await store.replace(key(), first.etag, b"old-writer", lease=old)
            saved = await store.replace(key(), first.etag, b"sending", lease=current)
            assert saved.data == b"sending"
    async with store.lease(key()) as later:
        assert later not in {old, current}


@pytest.mark.asyncio
async def test_operation_receipts_survive_export_expiry_and_have_no_implicit_deletion():
    records = PrivateRecords(MemoryObjectStore())
    await records.create(
        OWNER,
        RecordKind.OPERATION,
        ID,
        HASH,
        {"state": "unknown"},
        expires_at=None,
        now=NOW,
    )
    assert (
        await records.read(
            OWNER, RecordKind.OPERATION, ID, now=NOW + timedelta(days=365)
        )
    ).value["value"]["state"] == "unknown"
