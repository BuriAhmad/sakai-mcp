"""Durable send intent and read-only observations. This module never sends HTTP."""

from datetime import datetime
from typing import Any, Literal

from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.serialization import canonical, digest
from sakai_mcp.storage.base import RecordKind, RecordOwner
from sakai_mcp.storage.records import PrivateRecord, PrivateRecords

PROVENANCE = "existing-http-observation-v1"


class OperationJournal:
    def __init__(self, records: PrivateRecords) -> None:
        self.records = records

    async def prepare(
        self,
        owner: RecordOwner,
        operation_id: str,
        request: dict[str, Any],
        approved_hash: str,
        *,
        now: datetime,
    ) -> PrivateRecord:
        if digest(canonical(request)) != approved_hash:
            raise SakaiError(ErrorCode.CONFLICT)
        return await self.records.create(
            owner,
            RecordKind.OPERATION,
            operation_id,
            approved_hash,
            {
                "phase": "prepared",
                "request": request,
                "provenance": PROVENANCE,
                "ever_unknown": False,
                "observations": [],
                "guarantees": {
                    "native_compare_and_set": False,
                    "atomic_batch": False,
                    "readback_proves_causation": False,
                },
            },
            expires_at=None,
            now=now,
        )

    async def begin_send(
        self,
        owner: RecordOwner,
        operation_id: str,
        approved_hash: str,
        *,
        now: datetime,
    ) -> PrivateRecord:
        """Persist Sending before HTTP. Sending/Unknown is never a resend permit."""
        key = self.records.key(owner, RecordKind.OPERATION, operation_id)
        async with self.records.store.lease(key) as lease:
            current = await self.records.read(
                owner, RecordKind.OPERATION, operation_id, now=now
            )
            record = current.value
            value = record["value"]
            if (
                record["payload_hash"] != approved_hash
                or value.get("provenance") != PROVENANCE
                or value.get("phase") != "prepared"
            ):
                raise SakaiError(ErrorCode.CONFLICT)
            updated = {
                **record,
                "value": {
                    **value,
                    "phase": "sending",
                    "send_intent_at": now.isoformat(),
                },
            }
            saved = await self.records.store.replace(
                key, current.etag, canonical(updated), lease=lease
            )
            return self.records.checked(
                owner, RecordKind.OPERATION, operation_id, saved, now
            )

    async def unknown(
        self, owner: RecordOwner, operation_id: str, *, now: datetime
    ) -> PrivateRecord:
        return await self._observe(
            owner, operation_id, "unknown", {"reason": "outcome-unconfirmed"}, now=now
        )

    async def observe(
        self,
        owner: RecordOwner,
        operation_id: str,
        observation: dict[str, Any],
        *,
        partial: bool,
        now: datetime,
    ) -> PrivateRecord:
        """Caller supplies fresh read-only evidence; matching state is not attribution."""
        return await self._observe(
            owner,
            operation_id,
            "partial" if partial else "observed",
            observation,
            now=now,
        )

    async def _observe(
        self,
        owner: RecordOwner,
        operation_id: str,
        phase: Literal["unknown", "partial", "observed"],
        observation: dict[str, Any],
        *,
        now: datetime,
    ) -> PrivateRecord:
        key = self.records.key(owner, RecordKind.OPERATION, operation_id)
        async with self.records.store.lease(key) as lease:
            current = await self.records.read(
                owner, RecordKind.OPERATION, operation_id, now=now
            )
            record = current.value
            value = record["value"]
            if value.get("provenance") != PROVENANCE or value.get("phase") not in {
                "sending",
                "unknown",
                "partial",
                "observed",
            }:
                raise SakaiError(ErrorCode.CONFLICT)
            ever_unknown = value.get("ever_unknown") is True or phase == "unknown"
            observations = value.get("observations")
            if not isinstance(observations, list) or len(observations) >= 100:
                raise SakaiError(ErrorCode.CONFLICT)
            updated = {
                **record,
                "value": {
                    **value,
                    "phase": phase,
                    "ever_unknown": ever_unknown,
                    "attribution": "uncertain"
                    if ever_unknown
                    else "request-and-readback-observation",
                    "observations": [
                        *observations,
                        {"at": now.isoformat(), "evidence": observation},
                    ],
                },
            }
            data = canonical(updated)
            if len(data) > 1_000_000:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            saved = await self.records.store.replace(
                key, current.etag, data, lease=lease
            )
            return self.records.checked(
                owner, RecordKind.OPERATION, operation_id, saved, now
            )

    async def read(
        self, owner: RecordOwner, operation_id: str, *, now: datetime
    ) -> PrivateRecord:
        return await self.records.read(
            owner, RecordKind.OPERATION, operation_id, now=now
        )
