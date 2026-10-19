"""Default course facade, actor binding and existing native visit observations."""

import json

import httpx
import pytest

from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.client import SakaiClient
from tests.fixtures.authentication import settings
from tests.fixtures.sakai import FakeOBO, principal


def responses(request, *, public=False, functions=None):
    path = request.url.path
    if path == "/direct/user/current.json":
        return httpx.Response(200, json={"id": "native-uid", "eid": "synthetic-eid"})
    if path == "/api/users/me/sites":
        return httpx.Response(
            200,
            json={
                "sites": [
                    {"siteId": "project-a", "title": "Project", "project": True},
                    {"siteId": "course-b", "title": "Zoology", "course": True},
                    {"siteId": "course-a", "title": "Field Methods", "course": True},
                ]
            },
        )
    if path == "/direct/site.json":
        assert dict(request.url.params) == {
            "select": "access",
            "_start": "0",
            "_limit": "100",
        }
        return httpx.Response(200, json=[])
    if path.endswith("userPerms.json"):
        return httpx.Response(200, json=functions or ["site.visit"])
    if path.startswith("/direct/site/"):
        return httpx.Response(
            200,
            json={
                "id": path.rsplit("/", 1)[-1][:-5],
                "type": "course",
                "published": True,
                "pubView": public,
                "softlyDeleted": False,
            },
        )
    pytest.fail("Unapproved or legacy route used: " + path)


@pytest.mark.asyncio
async def test_default_course_facade_uses_only_existing_routes():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return responses(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = SakaiClient(settings(), FakeOBO(), http)
        rows = await client.courses.list_my_courses(principal())
        assert rows == [
            {"id": "course-a", "title": "Field Methods"},
            {"id": "course-b", "title": "Zoology"},
        ]
        await client.aclose()
    assert calls == [
        "/direct/user/current.json",
        "/api/users/me/sites",
        "/direct/site/course-a.json",
        "/direct/site/course-b.json",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure,code",
    [
        (403, ErrorCode.FORBIDDEN),
        (503, ErrorCode.DEPENDENCY_UNAVAILABLE),
        (200, ErrorCode.INTERNAL_ERROR),
    ],
)
async def test_existing_failure_has_no_legacy_fallback(failure, code):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/api/users/me/sites":
            return httpx.Response(
                failure,
                text="private incompatible response",
                headers={"content-type": "text/html"},
            )
        return responses(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SakaiError) as error:
            await SakaiClient(settings(), FakeOBO(), http).courses.list_my_courses(
                principal()
            )
    assert error.value.code == code
    assert not any("/mcp/v1/" in path for path in calls)


@pytest.mark.asyncio
async def test_actor_mismatch_never_returns_an_empty_successful_course_list():
    def handler(request):
        if request.url.path == "/direct/user/current.json":
            return httpx.Response(200, json={"id": "other", "eid": "other-eid"})
        pytest.fail("Actor mismatch reached course discovery")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SakaiError) as error:
            await SakaiClient(settings(), FakeOBO(), http).courses.list_my_courses(
                principal()
            )
    assert error.value.code == ErrorCode.FORBIDDEN


@pytest.mark.asyncio
async def test_revoked_or_removed_courses_are_filtered_using_native_denial():
    def handler(request):
        if request.url.path == "/direct/site/course-b.json":
            return httpx.Response(403)
        return responses(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        rows = await SakaiClient(settings(), FakeOBO(), http).courses.list_my_courses(
            principal()
        )
    assert rows == [{"id": "course-a", "title": "Field Methods"}]


@pytest.mark.asyncio
async def test_public_view_success_without_fresh_native_access_is_filtered():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: responses(request, public=True))
    ) as http:
        assert (
            await SakaiClient(settings(), FakeOBO(), http).courses.list_my_courses(
                principal()
            )
            == []
        )


@pytest.mark.asyncio
async def test_maintainer_public_course_uses_true_state_and_required_visit_function():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: responses(
                request, public=True, functions=["site.upd", "site.visit"]
            )
        )
    ) as http:
        rows = await SakaiClient(settings(), FakeOBO(), http).courses.list_my_courses(
            principal()
        )
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_deleted_public_course_requires_deleted_visit_even_for_maintainer():
    def handler(request):
        if request.url.path.startswith(
            "/direct/site/"
        ) and not request.url.path.endswith("userPerms.json"):
            return httpx.Response(
                200,
                json={
                    "id": request.url.path.rsplit("/", 1)[-1][:-5],
                    "type": "course",
                    "pubView": True,
                    "published": True,
                    "softlyDeleted": True,
                },
            )
        return responses(request, public=True, functions=["site.upd", "site.visit"])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        assert (
            await SakaiClient(settings(), FakeOBO(), http).courses.list_my_courses(
                principal()
            )
            == []
        )


@pytest.mark.asyncio
async def test_public_member_with_current_access_and_published_visit_permission_is_supported():
    def handler(request):
        if request.url.path == "/direct/site.json":
            return httpx.Response(
                200, json={"site_collection": [{"id": "course-a"}, {"id": "course-b"}]}
            )
        return responses(request, public=True, functions=["site.visit"])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        rows = await SakaiClient(settings(), FakeOBO(), http).courses.list_my_courses(
            principal()
        )
    assert [r["id"] for r in rows] == ["course-a", "course-b"]


@pytest.mark.asyncio
async def test_ambiguous_masked_public_state_is_not_silently_denied():
    def handler(request):
        result = responses(request, public=True, functions=["site.visit"])
        if request.url.path == "/direct/site/course-a.json":
            payload = json.loads(result.content)
            payload["published"] = False
            payload["id"] = ""
            payload["entityId"] = "course-a"
            return httpx.Response(200, json=payload)
        return result

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SakaiError) as caught:
            await SakaiClient(settings(), FakeOBO(), http).courses.list_my_courses(
                principal()
            )
        assert caught.value.code == ErrorCode.UNSUPPORTED_CAPABILITY


@pytest.mark.asyncio
async def test_course_cap_matches_original_first_500_after_visit_filter_and_utf16_sort():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/api/users/me/sites":
            return httpx.Response(
                200,
                json={
                    "sites": [
                        {
                            "siteId": f"course-{i:04}",
                            "title": f"Course {i:04}",
                            "course": True,
                        }
                        for i in range(502)
                    ]
                },
            )
        return responses(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        rows = await SakaiClient(settings(), FakeOBO(), http).courses.list_my_courses(
            principal()
        )
    assert len(rows) == 500 and rows[-1]["id"] == "course-0499"
    assert "/direct/site/course-0500.json" not in calls


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["paged", "duplicate", "saturated"])
async def test_public_access_lookup_paginates_and_rejects_drift_or_unbounded_inventory(
    mode,
):
    offsets = []

    def handler(request):
        if request.url.path == "/direct/site.json":
            offset = int(request.url.params["_start"])
            offsets.append(offset)
            if offset and mode == "paged":
                return httpx.Response(
                    200, json=[{"id": "course-a"}, {"id": "course-b"}]
                )
            if offset and mode == "duplicate":
                return httpx.Response(
                    200, json=[{"id": "unrelated-0"}, {"id": "course-a"}]
                )
            return httpx.Response(
                200,
                json=[{"id": f"unrelated-{i}"} for i in range(offset, offset + 100)],
            )
        return responses(request, public=True)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = SakaiClient(settings(), FakeOBO(), http)
        if mode == "paged":
            assert len(await client.courses.list_my_courses(principal())) == 2
            assert offsets == [0, 100, 0, 100]
        else:
            with pytest.raises(SakaiError) as caught:
                await client.courses.list_my_courses(principal())
            assert caught.value.code == (
                ErrorCode.CONFLICT
                if mode == "duplicate"
                else ErrorCode.UNSUPPORTED_CAPABILITY
            )
            assert len(offsets) == (2 if mode == "duplicate" else 20)


@pytest.mark.asyncio
async def test_public_access_lookup_does_not_treat_server_clamped_short_page_as_end():
    offsets = []

    def handler(request):
        if request.url.path == "/direct/site.json":
            offset = int(request.url.params["_start"])
            offsets.append(offset)
            return httpx.Response(
                200,
                json=[{"id": "unrelated"}]
                if offset == 0
                else [{"id": "course-a"}, {"id": "course-b"}],
            )
        return responses(request, public=True)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        assert (
            len(
                await SakaiClient(settings(), FakeOBO(), http).courses.list_my_courses(
                    principal()
                )
            )
            == 2
        )
    assert offsets == [0, 1, 0, 1]


@pytest.mark.asyncio
async def test_unpublished_public_member_requires_only_unpublished_visit_permission():
    def handler(request):
        if request.url.path == "/direct/site.json":
            return httpx.Response(200, json=[{"id": "course-a"}])
        if request.url.path == "/direct/site/course-a.json":
            return httpx.Response(
                200,
                json={
                    "id": "course-a",
                    "type": "course",
                    "pubView": True,
                    "published": False,
                    "softlyDeleted": False,
                },
            )
        return responses(request, public=True, functions=["site.visit.unp"])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        rows = await SakaiClient(settings(), FakeOBO(), http).courses.list_my_courses(
            principal()
        )
    assert rows == [{"id": "course-a", "title": "Field Methods"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata", [None, "course-b"])
async def test_masked_id_requires_matching_native_entity_metadata(metadata):
    def handler(request):
        if request.url.path == "/direct/site/course-a.json":
            return httpx.Response(
                200,
                json={
                    "id": "",
                    "entityId": metadata,
                    "type": "course",
                    "pubView": False,
                    "published": False,
                },
            )
        return responses(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        with pytest.raises(SakaiError) as caught:
            await SakaiClient(settings(), FakeOBO(), http).courses.list_my_courses(
                principal()
            )
        assert caught.value.code == ErrorCode.CONFLICT


@pytest.mark.asyncio
async def test_nonpublic_inherited_access_accepts_masked_id_with_exact_metadata():
    def handler(request):
        if request.url.path == "/direct/site/course-a.json":
            return httpx.Response(
                200,
                json={
                    "id": "",
                    "entityId": "course-a",
                    "type": "course",
                    "pubView": False,
                    "published": False,
                },
            )
        return responses(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        rows = await SakaiClient(settings(), FakeOBO(), http).courses.list_my_courses(
            principal()
        )
    assert [row["id"] for row in rows] == ["course-a", "course-b"]
