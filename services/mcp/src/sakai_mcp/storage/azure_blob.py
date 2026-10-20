"""Private Blob adapter. Construction performs no provisioning or network calls."""

import re
from contextlib import asynccontextmanager

from azure.core import MatchConditions
from azure.core.exceptions import AzureError, HttpResponseError
from azure.core.pipeline.transport import AioHttpTransport
from azure.identity.aio import ManagedIdentityCredential
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobLeaseClient, ContainerClient

from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.storage.base import LeaseIterator, ObjectKey, StoredObject

MAX_OBJECT_BYTES = 10 * 1024 * 1024


def _error(error: AzureError) -> SakaiError:
    status = error.status_code if isinstance(error, HttpResponseError) else None
    return SakaiError(
        ErrorCode.NOT_FOUND
        if status == 404
        else ErrorCode.CONFLICT
        if status in {409, 412}
        else ErrorCode.DEPENDENCY_UNAVAILABLE
    )


class AzureBlobObjectStore:
    def __init__(
        self,
        client: ContainerClient,
        credential: ManagedIdentityCredential | None = None,
    ) -> None:
        # Injected clients are for local tests; production uses managed_identity.
        self._client = client
        self._credential = credential

    @classmethod
    def managed_identity(
        cls, account_url: str, container: str, *, client_id: str | None = None
    ) -> "AzureBlobObjectStore":
        if not re.fullmatch(
            r"https://[a-z0-9]{3,24}\.blob\.core\.windows\.net", account_url
        ) or not re.fullmatch(r"[a-z0-9](?:[a-z0-9]|-(?!-)){1,61}[a-z0-9]", container):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        credential = ManagedIdentityCredential(client_id=client_id)
        client = ContainerClient(
            account_url,
            container,
            credential=credential,
            transport=AioHttpTransport(
                use_env_settings=False, connection_timeout=5, read_timeout=15
            ),
            retry_total=0,
            logging_enable=False,
            max_single_get_size=1024 * 1024,
            max_chunk_get_size=1024 * 1024,
        )
        return cls(client, credential)

    async def _write(
        self,
        key: ObjectKey,
        data: bytes,
        *,
        etag: str | None = None,
        lease: str | None = None,
    ) -> StoredObject:
        if len(data) > MAX_OBJECT_BYTES:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if etag is not None and (
            key.artifact_id is not None or not etag or etag == "*"
        ):
            raise SakaiError(ErrorCode.CONFLICT)
        blob = self._client.get_blob_client(key.path())
        try:
            result = await blob.upload_blob(
                data,
                overwrite=etag is not None,
                lease=BlobLeaseClient(blob, lease_id=lease) if lease else None,
                etag=etag,
                match_condition=MatchConditions.IfNotModified if etag else None,
                content_settings=ContentSettings(
                    content_type="application/octet-stream", cache_control="no-store"
                ),
                logging_enable=False,
            )
            return StoredObject(bytes(data), result["etag"])
        except AzureError as error:
            # A lost response may have committed. Do not retry: caller reconciles
            # the conditional object before deciding whether another send is safe.
            raise _error(error) from None

    async def create(self, key: ObjectKey, data: bytes) -> StoredObject:
        return await self._write(key, data)

    async def replace(
        self, key: ObjectKey, etag: str, data: bytes, *, lease: str | None = None
    ) -> StoredObject:
        if not etag:
            raise SakaiError(ErrorCode.CONFLICT)
        return await self._write(key, data, etag=etag, lease=lease)

    async def read(self, key: ObjectKey) -> StoredObject:
        blob = self._client.get_blob_client(key.path())
        try:
            props = await blob.get_blob_properties(logging_enable=False)
            if props.size is None or not 0 <= props.size <= MAX_OBJECT_BYTES:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            stream = await blob.download_blob(
                etag=props.etag,
                match_condition=MatchConditions.IfNotModified,
                max_concurrency=1,
                logging_enable=False,
            )
            chunks = bytearray()
            async for chunk in stream.chunks():
                if len(chunks) + len(chunk) > props.size:
                    raise SakaiError(ErrorCode.CONFLICT)
                chunks.extend(chunk)
            if len(chunks) != props.size:
                raise SakaiError(ErrorCode.CONFLICT)
            return StoredObject(bytes(chunks), props.etag)
        except AzureError as error:
            raise _error(error) from None

    @asynccontextmanager
    async def lease(self, key: ObjectKey, *, seconds: int = 30) -> LeaseIterator:
        if (
            type(seconds) is not int
            or not 15 <= seconds <= 60
            or key.artifact_id is not None
        ):
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        try:
            lease = await self._client.get_blob_client(key.path()).acquire_lease(
                lease_duration=seconds, logging_enable=False
            )
        except AzureError as error:
            raise _error(error) from None
        completed = False
        try:
            yield lease.id
            completed = True
        finally:
            try:
                await lease.release(logging_enable=False)
            except AzureError as error:
                if completed:
                    raise _error(error) from None
                # Preserve the primary failure. Finite native lease expires.

    async def aclose(self) -> None:
        try:
            await self._client.close()
        finally:
            if self._credential is not None:
                await self._credential.close()
