"""Deterministic conditional-store test adapter. Never a production durable backend."""

import asyncio
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.storage.base import LeaseIterator, ObjectKey, StoredObject


class MemoryObjectStore:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._objects: dict[str, StoredObject] = {}
        self._leases: dict[str, tuple[str, float]] = {}
        self._lock = asyncio.Lock()
        self._clock = clock

    async def create(self, key: ObjectKey, data: bytes) -> StoredObject:
        path = key.path()
        async with self._lock:
            if path in self._objects:
                raise SakaiError(ErrorCode.CONFLICT)
            result = StoredObject(bytes(data), str(uuid4()))
            self._objects[path] = result
            return result

    async def read(self, key: ObjectKey) -> StoredObject:
        async with self._lock:
            try:
                return self._objects[key.path()]
            except KeyError:
                raise SakaiError(ErrorCode.NOT_FOUND) from None

    async def replace(
        self, key: ObjectKey, etag: str, data: bytes, *, lease: str | None = None
    ) -> StoredObject:
        path = key.path()
        if key.artifact_id is not None:
            raise SakaiError(ErrorCode.CONFLICT)  # Captured bytes are immutable.
        async with self._lock:
            existing = self._objects.get(path)
            if existing is None:
                raise SakaiError(ErrorCode.NOT_FOUND)
            active = self._leases.get(path)
            if active is not None and self._clock() >= active[1]:
                self._leases.pop(path)
                active = None
            if (active is not None and active[0] != lease) or (
                lease is not None and (active is None or active[0] != lease)
            ):
                raise SakaiError(ErrorCode.CONFLICT)
            if existing.etag != etag:
                raise SakaiError(ErrorCode.CONFLICT)
            result = StoredObject(bytes(data), str(uuid4()))
            self._objects[path] = result
            return result

    @asynccontextmanager
    async def lease(self, key: ObjectKey, *, seconds: int = 30) -> LeaseIterator:
        if (
            type(seconds) is not int
            or not 15 <= seconds <= 60
            or key.artifact_id is not None
        ):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        path = key.path()
        async with self._lock:
            if path not in self._objects:
                raise SakaiError(ErrorCode.NOT_FOUND)
            active = self._leases.get(path)
            if active is not None and self._clock() < active[1]:
                raise SakaiError(ErrorCode.CONFLICT)
            token = str(uuid4())
            self._leases[path] = (token, self._clock() + seconds)
        try:
            yield token
        finally:
            async with self._lock:
                if self._leases.get(path, (None,))[0] == token:
                    self._leases.pop(path)

    async def aclose(self) -> None:
        pass
