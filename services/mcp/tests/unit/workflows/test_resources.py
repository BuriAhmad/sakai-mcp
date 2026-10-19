"""Export paging must preserve snapshot identity and bounded immutable evidence."""

import asyncio
from types import SimpleNamespace

import pytest

from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.workflows.resources import export_manifest
from tests.fixtures import grading_data as f
from tests.fixtures.sakai import principal


@pytest.mark.parametrize("failure", [None, "snapshot", "duplicate", "cursor", "budget"])
def test_manifest_aggregation_checks_all_pages(failure):
    first = f.manifest().model_copy(update={"next_cursor": "page-two"})
    artifact = first.artifacts[0].model_copy(update={"artifact_id": "second-artifact"})
    second = first.model_copy(update={"artifacts": [artifact], "next_cursor": None})
    if failure == "snapshot":
        second = second.model_copy(update={"request_sha256": "a" * 64})
    elif failure == "duplicate":
        second = second.model_copy(update={"artifacts": first.artifacts})
    elif failure == "cursor":
        second = second.model_copy(update={"next_cursor": "page-two"})
    elif failure == "budget":
        second = second.model_copy(
            update={
                "artifacts": [
                    artifact.model_copy(update={"size_bytes": 100 * 1024 * 1024 + 1})
                ]
            }
        )
    cursors = []

    class Gateway:
        async def get_assignment_submission_export(self, token, request):
            cursors.append(request.cursor)
            assert request.limit == 100
            return first if request.cursor is None else second

    client = SimpleNamespace(grading=Gateway())
    if failure:
        with pytest.raises(SakaiError) as error:
            asyncio.run(
                export_manifest(client, principal(), f.COURSE, f.ASSIGNMENT, f.EXPORT)
            )
        assert error.value.code == (
            ErrorCode.UNSUPPORTED_CAPABILITY
            if failure == "budget"
            else ErrorCode.CONFLICT
        )
    else:
        result = asyncio.run(
            export_manifest(client, principal(), f.COURSE, f.ASSIGNMENT, f.EXPORT)
        )
        assert [a.artifact_id for a in result.artifacts] == [
            f.ARTIFACT,
            "second-artifact",
        ]
        assert result.next_cursor is None
    assert cursors == [None, "page-two"]
