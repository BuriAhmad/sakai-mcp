"""Conditional private-object storage contract independent of a deployed backend."""

import hashlib
import re
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from sakai_mcp.errors import ErrorCode, SakaiError


class RecordKind(StrEnum):
    EXPORT = "export"
    PROPOSAL = "proposal"
    OPERATION = "operation"


@dataclass(frozen=True, repr=False)
class RecordOwner:
    tenant: str
    object_id: str
    sakai_uid: str
    course: str
    assignment: str

    def namespace(self) -> str:
        values = (
            self.tenant,
            self.object_id,
            self.sakai_uid,
            self.course,
            self.assignment,
        )
        if any(
            not isinstance(v, str)
            or not v
            or len(v) > 255
            or any(ord(c) < 32 or ord(c) == 127 for c in v)
            for v in values
        ):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        return hashlib.sha256(
            ("sakai-private-owner-v1\0" + "\0".join(values)).encode()
        ).hexdigest()


def identifier(value: str) -> str:
    try:
        normalized = str(UUID(value))
        if value != normalized:
            raise ValueError
        return normalized
    except (ValueError, TypeError, AttributeError):
        raise SakaiError(ErrorCode.VALIDATION_ERROR) from None


@dataclass(frozen=True, repr=False)
class ObjectKey:
    namespace: str
    kind: RecordKind
    record_id: str
    artifact_id: str | None = None

    def path(self) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", self.namespace) or not isinstance(
            self.kind, RecordKind
        ):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        suffix = (
            "record.json"
            if self.artifact_id is None
            else "artifacts/" + identifier(self.artifact_id)
        )
        return f"v1/{self.namespace}/{self.kind}/{identifier(self.record_id)}/{suffix}"


@dataclass(frozen=True)
class StoredObject:
    data: bytes = field(repr=False)
    etag: str


class ObjectStore(Protocol):
    async def create(self, key: ObjectKey, data: bytes) -> StoredObject:
        """Create iff absent; never overwrite. Existing keys raise CONFLICT."""
        ...

    async def read(self, key: ObjectKey) -> StoredObject: ...

    async def replace(
        self, key: ObjectKey, etag: str, data: bytes, *, lease: str | None = None
    ) -> StoredObject:
        """ETag match and, when leased, the current lease are both required."""
        ...

    def lease(
        self, key: ObjectKey, *, seconds: int = 30
    ) -> AbstractAsyncContextManager[str]: ...

    async def aclose(self) -> None: ...


# Protocol deliberately has no delete/list-public/SAS/URL or native write method.
# Retention/deletion and source authorization are separate reviewed workflows.
LeaseIterator = AsyncIterator[str]
