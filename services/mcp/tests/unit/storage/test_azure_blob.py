"""SDK boundary checks without Azure credentials, requests or stored records."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from azure.core import MatchConditions
from azure.core.exceptions import HttpResponseError, ServiceResponseError

from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.storage.azure_blob import MAX_OBJECT_BYTES, AzureBlobObjectStore
from sakai_mcp.storage.base import ObjectKey, RecordKind

KEY = ObjectKey("a" * 64, RecordKind.OPERATION, "11111111-1111-4111-8111-111111111111")


def adapter():
    blob = Mock()
    blob.upload_blob = AsyncMock(return_value={"etag": '"v2"'})
    blob.get_blob_properties = AsyncMock(
        return_value=SimpleNamespace(size=3, etag='"v1"')
    )
    blob.download_blob = AsyncMock()
    blob.acquire_lease = AsyncMock()
    container = Mock(get_blob_client=Mock(return_value=blob), close=AsyncMock())
    return AzureBlobObjectStore(container), container, blob


@pytest.mark.asyncio
async def test_conditional_create_replace_and_lease_fencing():
    store, container, blob = adapter()
    await store.create(KEY, b"one")
    assert blob.upload_blob.call_args.kwargs["overwrite"] is False
    await store.replace(KEY, '"v1"', b"two", lease="lease-token")
    options = blob.upload_blob.call_args.kwargs
    assert options["overwrite"] is True and options["etag"] == '"v1"'
    assert options["match_condition"] == MatchConditions.IfNotModified
    assert options["lease"].id == "lease-token"
    assert options["content_settings"].cache_control == "no-store"
    assert container.get_blob_client.call_args.args == (KEY.path(),)
    for invalid in ["", "*"]:
        with pytest.raises(SakaiError):
            await store.replace(KEY, invalid, b"bad")
    artifact = ObjectKey(KEY.namespace, KEY.kind, KEY.record_id, KEY.record_id)
    with pytest.raises(SakaiError):
        await store.replace(artifact, '"v1"', b"bad")


@pytest.mark.asyncio
async def test_lost_write_response_is_not_replayed_and_errors_are_sanitized():
    store, _, blob = adapter()
    for failure, code in [
        (ServiceResponseError("private URL"), ErrorCode.DEPENDENCY_UNAVAILABLE),
        (HttpResponseError("private", status_code=412), ErrorCode.CONFLICT),
        (HttpResponseError("private", status_code=404), ErrorCode.NOT_FOUND),
    ]:
        # AzureError status_code is normally populated from a response object.
        if isinstance(failure, HttpResponseError):
            failure.status_code = 412 if code == ErrorCode.CONFLICT else 404
        blob.upload_blob.reset_mock()
        blob.upload_blob.side_effect = failure
        with pytest.raises(SakaiError) as caught:
            await store.create(KEY, b"one")
        assert caught.value.code == code and "private" not in str(caught.value)
        blob.upload_blob.assert_awaited_once()


@pytest.mark.asyncio
async def test_read_is_bounded_and_pins_etag_through_download():
    store, _, blob = adapter()

    async def chunks():
        yield b"o"
        yield b"ne"

    blob.download_blob.return_value.chunks = chunks
    saved = await store.read(KEY)
    assert saved.data == b"one" and saved.etag == '"v1"'
    assert blob.download_blob.call_args.kwargs["etag"] == '"v1"'
    assert (
        blob.download_blob.call_args.kwargs["match_condition"]
        == MatchConditions.IfNotModified
    )
    blob.get_blob_properties.return_value.size = MAX_OBJECT_BYTES + 1
    with pytest.raises(SakaiError) as caught:
        await store.read(KEY)
    assert caught.value.code == ErrorCode.UNSUPPORTED_CAPABILITY
    blob.get_blob_properties.return_value.size = 2
    with pytest.raises(SakaiError) as caught:
        await store.read(KEY)
    assert caught.value.code == ErrorCode.CONFLICT


@pytest.mark.asyncio
async def test_finite_lease_release_preserves_primary_error():
    store, _, blob = adapter()
    lease = SimpleNamespace(id="lease", release=AsyncMock())
    blob.acquire_lease.return_value = lease
    async with store.lease(KEY, seconds=15) as token:
        assert token == "lease"
    assert blob.acquire_lease.call_args.kwargs["lease_duration"] == 15
    lease.release.assert_awaited_once()
    lease.release.side_effect = ServiceResponseError("private")
    with pytest.raises(ValueError, match="primary"):
        async with store.lease(KEY):
            raise ValueError("primary")
    with pytest.raises(SakaiError):
        async with store.lease(KEY, seconds=-1):
            pytest.fail("infinite lease accepted")


def test_only_trusted_configured_blob_origins_without_sas_or_paths():
    for url in [
        "http://account.blob.core.windows.net",
        "https://evil.test",
        "https://account.blob.core.windows.net/?sig=secret",
        "https://account.blob.core.windows.net/path",
    ]:
        with pytest.raises(SakaiError):
            AzureBlobObjectStore.managed_identity(url, "private")


@pytest.mark.asyncio
async def test_lifecycle_closes_credential_even_on_client_failure():
    store, container, _ = adapter()
    store._credential = SimpleNamespace(close=AsyncMock())
    container.close.side_effect = RuntimeError("client close")
    with pytest.raises(RuntimeError):
        await store.aclose()
    store._credential.close.assert_awaited_once()
