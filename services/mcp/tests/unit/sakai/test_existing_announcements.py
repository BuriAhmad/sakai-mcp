"""Public announcement facade, exact native DTO mapping and scope failures."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from sakai_mcp.contracts.announcements import OBSERVATION_CAP, announcement_rows
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.client import SakaiClient
from tests.fixtures.authentication import settings
from tests.fixtures.sakai import FakeOBO, principal

ROW = {
    "announcementId": "message-a",
    "id": "course-a:main:message-a",
    "siteId": "course-a",
    "channel": "main",
    "title": "Literal & <title>",
    "body": "<p>untrusted</p>\r\n",
    "createdOn": 1790000000123,
}


def test_native_message_id_body_and_milliseconds_are_preserved_without_merged_rows():
    neighbor = {**ROW, "siteId": "neighbor", "announcementId": "merged"}
    other_channel = {**ROW, "channel": "other", "announcementId": "other-channel"}
    rows = announcement_rows(
        {
            "entityPrefix": "announcement",
            "announcement_collection": [neighbor, ROW, other_channel],
        },
        "course-a",
    )
    assert rows == [
        {
            "id": "message-a",
            "title": ROW["title"],
            "body": ROW["body"],
            "postedAt": 1790000000123,
        }
    ]


@pytest.mark.parametrize(
    "date", [None, "1790000000123", 1790000000.123, True, -1, 10**40]
)
def test_unproven_or_invalid_date_never_becomes_a_plausible_timestamp(date):
    with pytest.raises(SakaiError):
        announcement_rows([{**ROW, "createdOn": date}], "course-a")


def test_duplicate_ids_saturated_observation_and_wrong_envelopes_fail_explicitly():
    for value in [
        [ROW, ROW],
        [ROW] * OBSERVATION_CAP,
        {"entityPrefix": "other", "announcement_collection": []},
        {"announcements": [ROW]},
    ]:
        with pytest.raises(SakaiError):
            announcement_rows(value, "course-a")


@pytest.mark.asyncio
async def test_public_facade_reauthorizes_and_calls_only_existing_fixed_read():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert request.method == "GET" and "cookie" not in request.headers
        if request.url.path == "/direct/user/current.json":
            return httpx.Response(200, json={"id": "uid", "eid": "synthetic-eid"})
        if request.url.path == "/direct/site/course-a.json":
            return httpx.Response(
                200,
                json={
                    "id": "course-a",
                    "type": "course",
                    "pubView": False,
                    "published": True,
                },
            )
        assert request.url.path == "/direct/announcement/site/course-a.json"
        assert dict(request.url.params) == {"n": "1000", "d": "3650", "a": "0"}
        return httpx.Response(200, json=[deepcopy(ROW)])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = SakaiClient(settings(), FakeOBO(), http)
        result = await client.announcements.get_course_announcements(
            principal(), "course-a"
        )
        assert result[0]["id"] == "message-a"
        await client.aclose()
    assert calls == [
        "/direct/user/current.json",
        "/direct/site/course-a.json",
        "/direct/announcement/site/course-a.json",
    ]


@pytest.mark.asyncio
async def test_revoked_or_invalid_source_has_no_legacy_fallback():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/direct/user/current.json":
            return httpx.Response(200, json={"id": "uid", "eid": "synthetic-eid"})
        return httpx.Response(403)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = SakaiClient(settings(), FakeOBO(), http)
        with pytest.raises(SakaiError) as caught:
            await client.announcements.get_course_announcements(principal(), "course-a")
        assert caught.value.code == ErrorCode.FORBIDDEN
    assert len(calls) == 2 and not any("/mcp/v1/" in path for path in calls)


def test_python_window_excludes_old_and_future_dates_even_without_native_release_property():
    now = datetime(2026, 10, 18, tzinfo=UTC)
    rows = [
        ROW,
        {
            **ROW,
            "announcementId": "old",
            "createdOn": int((now - timedelta(days=3651)).timestamp() * 1000),
        },
        {
            **ROW,
            "announcementId": "future",
            "createdOn": int((now + timedelta(days=1)).timestamp() * 1000),
        },
    ]
    assert [r["id"] for r in announcement_rows(rows, "course-a", now=now)] == [
        "message-a"
    ]
