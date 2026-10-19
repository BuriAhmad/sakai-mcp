"""Placement relation/ambiguity checks and existing-HTTP discovery integration."""

from copy import deepcopy

import httpx
import pytest

from sakai_mcp.contracts.placements import placement
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.existing_transport import ExistingApiTransport
from sakai_mcp.workflows.placements import PlacementDiscovery
from tests.fixtures.authentication import settings
from tests.fixtures.sakai import FakeOBO, principal

ORIGIN = "https://sakai.example.test"
URL = ORIGIN + "/portal/site/course-a/page/page-a"
PAGES = [
    {
        "id": "page-a",
        "siteId": "course-a",
        "url": URL,
        "tools": [
            {
                "id": "placement-a",
                "placementId": "placement-a",
                "toolId": "sakai.announcements",
                "context": "course-a",
                "pageId": "page-a",
                "siteId": "course-a",
                "url": URL,
            },
            {
                "id": "placement-b",
                "placementId": "placement-b",
                "toolId": "sakai.assignment.grades",
                "context": "course-a",
                "pageId": "page-a",
                "siteId": "course-a",
                "url": URL,
            },
        ],
    }
]


def test_multitool_page_resolves_by_native_id_and_not_title_or_page_url():
    target = placement(PAGES, "course-a", "sakai.announcements", ORIGIN)
    assert target.placement == "placement-a"
    assert target.url == ORIGIN + "/portal/tool/placement-a"
    assert "placement-a" not in repr(target)


@pytest.mark.parametrize(
    "field,bad",
    [
        ("id", "other"),
        ("placementId", "other"),
        ("siteId", "other"),
        ("context", "other"),
        ("pageId", "other"),
        ("url", "https://evil.example/portal/site/course-a/page/page-a"),
        ("url", URL + "?props=true"),
        ("url", URL + ";jsessionid=borrowed"),
    ],
)
def test_neighbor_scope_or_foreign_url_never_becomes_a_placement(field, bad):
    pages = deepcopy(PAGES)
    pages[0]["tools"][0][field] = bad
    with pytest.raises(SakaiError) as caught:
        placement(pages, "course-a", "sakai.announcements", ORIGIN)
    assert caught.value.code == ErrorCode.CONFLICT


def test_missing_ambiguous_duplicate_or_unproven_envelope_fails():
    for pages in [[], {"site_collection": PAGES}, PAGES + PAGES]:
        with pytest.raises(SakaiError):
            placement(pages, "course-a", "sakai.announcements", ORIGIN)
    pages = deepcopy(PAGES)
    second = deepcopy(pages[0]["tools"][0])
    second.update(id="second", placementId="second")
    pages[0]["tools"].append(second)
    with pytest.raises(SakaiError) as caught:
        placement(pages, "course-a", "sakai.announcements", ORIGIN)
    assert caught.value.code == ErrorCode.CONFLICT
    with pytest.raises(SakaiError):
        placement(PAGES, "course-a", "sakai.admin", ORIGIN)


@pytest.mark.asyncio
async def test_resolver_fresh_actor_visit_then_pages_no_admin_options():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        assert not request.url.query
        if request.url.path == "/direct/user/current.json":
            return httpx.Response(
                200, json={"id": "native-uid", "eid": "synthetic-eid"}
            )
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
        assert request.url.path == "/direct/site/course-a/pages.json"
        return httpx.Response(200, json=PAGES)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        configured = settings(sakai_base_url=ORIGIN)
        bound = await PlacementDiscovery(
            ExistingApiTransport(configured, FakeOBO(), http)
        ).resolve(principal(), "course-a", "sakai.announcements")
    assert (
        bound.access.actor.uid == "native-uid"
        and bound.target.placement == "placement-a"
    )
    assert calls == [
        "/direct/user/current.json",
        "/direct/site/course-a.json",
        "/direct/site/course-a/pages.json",
    ]


@pytest.mark.asyncio
async def test_revoked_visit_prevents_even_pages_discovery():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/direct/user/current.json":
            return httpx.Response(
                200, json={"id": "native-uid", "eid": "synthetic-eid"}
            )
        return httpx.Response(403)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SakaiError):
            await PlacementDiscovery(
                ExistingApiTransport(settings(), FakeOBO(), http)
            ).resolve(principal(), "course-a", "sakai.announcements")
    assert not any(path.endswith("/pages.json") for path in calls)
