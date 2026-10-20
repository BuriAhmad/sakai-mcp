"""Versioned private records with owner, payload, immutability and expiry checks."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.serialization import canonical
from sakai_mcp.storage.base import (
    ObjectKey,
    ObjectStore,
    RecordKind,
    RecordOwner,
    StoredObject,
)


@dataclass(frozen=True)
class PrivateRecord:
    value: dict[str, Any] = field(repr=False)
    etag: str


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError


def _read_json(data: bytes) -> dict[str, Any]:
    if len(data) > 1_000_000:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    try:
        value = json.loads(
            data.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant
        )
        if not isinstance(value, dict):
            raise TypeError
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise SakaiError(ErrorCode.INTERNAL_ERROR) from None


class PrivateRecords:
    def __init__(self, store: ObjectStore) -> None:
        self.store = store

    def key(
        self,
        owner: RecordOwner,
        kind: RecordKind,
        record_id: str,
        artifact: str | None = None,
    ) -> ObjectKey:
        return ObjectKey(owner.namespace(), kind, record_id, artifact)

    async def create(
        self,
        owner: RecordOwner,
        kind: RecordKind,
        record_id: str,
        payload_hash: str,
        value: dict[str, Any],
        *,
        expires_at: datetime | None,
        now: datetime,
    ) -> PrivateRecord:
        if now.tzinfo is None or not re.fullmatch(r"[0-9a-f]{64}", payload_hash):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        if expires_at is not None and (
            expires_at.tzinfo is None or expires_at.utcoffset() is None
        ):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        if kind != RecordKind.OPERATION and expires_at is None:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        if kind != RecordKind.OPERATION and (
            expires_at is None
            or expires_at <= now
            or expires_at > now + timedelta(hours=24)
        ):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        record = {
            "schema": "sakai-private-record-v1",
            "owner": owner.namespace(),
            "kind": kind.value,
            "id": record_id,
            "payload_hash": payload_hash,
            "expires_at": expires_at.astimezone(UTC).isoformat()
            if expires_at
            else None,
            "created_at": now.astimezone(UTC).isoformat(),
            "value": value,
        }
        data = canonical(record)
        if len(data) > 1_000_000:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        key = self.key(owner, kind, record_id)
        try:
            saved = await self.store.create(key, data)
        except SakaiError as error:
            if error.code != ErrorCode.CONFLICT:
                raise
            # Same request ID retrieves its historical outcome, never recaptures
            # bytes or resets expiry against a newer source.
            saved = await self.store.read(key)
            previous = _read_json(saved.data)
            if previous.get("payload_hash") != payload_hash:
                raise SakaiError(ErrorCode.CONFLICT) from None
        return self.checked(owner, kind, record_id, saved, now)

    def checked(
        self,
        owner: RecordOwner,
        kind: RecordKind,
        record_id: str,
        saved: StoredObject,
        now: datetime | None,
    ) -> PrivateRecord:
        record = _read_json(saved.data)
        if (
            record.get("schema") != "sakai-private-record-v1"
            or record.get("owner") != owner.namespace()
            or record.get("kind") != kind.value
            or record.get("id") != record_id
            or not isinstance(record.get("value"), dict)
        ):
            raise SakaiError(ErrorCode.CONFLICT)
        expires = record.get("expires_at")
        if now is not None and expires is not None:
            try:
                expiry = datetime.fromisoformat(expires)
                if expiry.tzinfo is None or now.tzinfo is None:
                    raise ValueError
                if now >= expiry:
                    raise SakaiError(ErrorCode.NOT_FOUND)
            except (ValueError, TypeError):
                raise SakaiError(ErrorCode.CONFLICT) from None
        if expires is None and kind != RecordKind.OPERATION:
            raise SakaiError(ErrorCode.CONFLICT)
        return PrivateRecord(record, saved.etag)

    async def read(
        self, owner: RecordOwner, kind: RecordKind, record_id: str, *, now: datetime
    ) -> PrivateRecord:
        # Caller must freshly authorize the source scope first. This layer never
        # treats an owner hash or known UUID as a native permission grant.
        saved = await self.store.read(self.key(owner, kind, record_id))
        return self.checked(owner, kind, record_id, saved, now)

    async def artifact(
        self,
        owner: RecordOwner,
        export: str,
        artifact: str,
        *,
        expected_size: int,
        expected_sha256: str,
        now: datetime,
    ) -> bytes:
        await self.read(owner, RecordKind.EXPORT, export, now=now)
        saved = await self.store.read(
            self.key(owner, RecordKind.EXPORT, export, artifact)
        )
        if (
            len(saved.data) != expected_size
            or hashlib.sha256(saved.data).hexdigest() != expected_sha256
        ):
            raise SakaiError(ErrorCode.CONFLICT)
        return saved.data
