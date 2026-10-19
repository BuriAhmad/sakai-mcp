"""Compare actual SDK discovery and deterministic output with the pre-refactor baseline."""

import asyncio
import inspect
import json
from pathlib import Path

import pytest

from sakai_mcp.grading.evaluator import evaluate_mcq
from sakai_mcp.grading.reports import report_csv
from sakai_mcp.grading.serialization import canonical, digest
from sakai_mcp.mcp.server import create_server
from sakai_mcp.security.auth import EntraTokenVerifier
from tests.fixtures import grading_data as f
from tests.fixtures.authentication import settings
from tests.fixtures.sakai import FakeClient

CONTRACTS = Path(__file__).parents[1] / "contracts"


@pytest.mark.parametrize(
    "setup,grading", [(False, False), (True, False), (False, True), (True, True)]
)
def test_discovered_catalog_and_schemas_match_baseline(setup, grading):
    baseline = json.loads((CONTRACTS / "catalog.json").read_text())
    config = settings(
        assignment_setup_enabled=setup, assignment_grading_enabled=grading
    )
    server = create_server(
        config, FakeClient(), EntraTokenVerifier(config, lambda _: None)
    )
    tools = asyncio.run(server.list_tools())
    templates = asyncio.run(server.list_resource_templates())
    expected = baseline[f"{int(setup)}{int(grading)}"]
    assert [t.name for t in tools] == expected["tools"]
    assert [
        t.model_dump(mode="json", by_alias=True, exclude_none=True) for t in templates
    ] == expected["templates"]
    definitions = {t["name"]: t for t in baseline["definitions"]}
    for tool in tools:
        assert (
            tool.model_dump(mode="json", by_alias=True, exclude_none=True)
            == definitions[tool.name]
        )


def test_grading_bytes_and_evaluator_provenance_match_baseline():
    expected = json.loads((CONTRACTS / "grading.json").read_text())
    manifest = f.manifest().model_dump()
    manifest.update(course_id=f.COURSE, assignment_id=f.ASSIGNMENT)
    for artifact in manifest["artifacts"]:
        artifact.pop("download_path")
        artifact.pop("relative_path")
    rows = evaluate_mcq(
        f.config().model_dump(),
        f.context().model_dump(),
        [r.model_dump() for r in f.roster().items],
        manifest,
        {f.ARTIFACT: f.DATA},
    )
    assert rows == expected["rows"]
    assert report_csv(rows) == expected["csv"]
    assert digest(canonical(rows)) == expected["canonical_sha256"]
    assert digest(inspect.getsource(evaluate_mcq).encode()) == expected["engine_sha256"]
