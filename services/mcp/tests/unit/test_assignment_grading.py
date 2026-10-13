import asyncio
import hashlib
import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError
from starlette.applications import Starlette

from sakai_mcp.auth import EntraTokenVerifier
from sakai_mcp.grading_artifacts import artifact_route
from sakai_mcp.grading_models import (
    CONTRACTS,
    FeedbackPatch,
    SaveAssignmentGradesRequest,
)
from sakai_mcp.grading_workspace import grade_mcq, payload_hash, private_workspace
from sakai_mcp.sakai_client import ErrorCode, SakaiClient, SakaiError
from sakai_mcp.server import create_server
from tests.helpers import settings
from tests.protocol.test_server import FakeClient
from tests.unit.test_sakai_client import FakeOBO, principal


@pytest.mark.parametrize(
    "setup,grading,count",
    [(False, False, 5), (True, False, 8), (False, True, 14), (True, True, 17)],
)
def test_independent_catalog_gates(setup, grading, count):
    config = settings(
        assignment_setup_enabled=setup, assignment_grading_enabled=grading
    )
    server = create_server(
        config, FakeClient(), EntraTokenVerifier(config, lambda _: None)
    )
    catalog = asyncio.run(server.list_tools())
    assert len(catalog) == count
    assert (set(CONTRACTS) <= {t.name for t in catalog}) == grading
    if grading:
        save = next(t for t in catalog if t.name == "save_assignment_grades")
        assert (
            save.annotations.read_only_hint is False
            and save.annotations.idempotent_hint is False
        )
        assert "expected_grade_revision" in str(save.input_schema)
        assert "invoke" not in save.input_schema["properties"]


def test_disabled_grading_has_no_network_calls():
    calls = []
    client = SakaiClient(
        settings(),
        FakeOBO(),
        httpx.AsyncClient(transport=httpx.MockTransport(lambda r: calls.append(r))),
    )
    model = CONTRACTS["get_assignment_grading_context"][0](
        course_id="course-a", assignment_id="assignment-a"
    )
    with pytest.raises(SakaiError) as error:
        asyncio.run(
            client.grading_request("get_assignment_grading_context", principal(), model)
        )
    assert error.value.code == ErrorCode.UNSUPPORTED_CAPABILITY and not calls


def save_request(score="4"):
    grades = [
        {
            "submission_id": "submission-a",
            "sakai_user_id": "student-a",
            "expected_content_revision": "content",
            "expected_grade_revision": "grade",
            "score": score,
            "feedback": {"action": "preserve", "text": None},
        }
    ]
    return {
        "course_id": "course-a",
        "assignment_id": "assignment-a",
        "operation_id": "00000000-0000-0000-0000-000000000001",
        "mode": "commit",
        "expected_assignment_revision": "config",
        "payload_sha256": payload_hash(
            "save", "course-a", "assignment-a", "config", grades
        ),
        "grades": grades,
    }


@pytest.mark.parametrize("score", [True, 4, 4.5, "NaN", "Infinity", "-1", "04"])
def test_scores_are_strict_exact_decimal_strings(score):
    with pytest.raises(ValidationError):
        SaveAssignmentGradesRequest.model_validate(save_request(score))


@pytest.mark.parametrize(
    "action,text",
    [("preserve", "overwrite"), ("clear", "overwrite"), ("replace", None)],
)
def test_feedback_patch_does_not_clear_omitted_fields(action, text):
    with pytest.raises(ValidationError):
        FeedbackPatch(action=action, text=text)


def test_partial_receipt_preserves_rows_and_post_is_not_replayed():
    calls = []
    request = SaveAssignmentGradesRequest.model_validate(save_request())
    receipt = {
        "operation_id": request.operation_id,
        "kind": "save",
        "mode": "commit",
        "payload_sha256": request.payload_sha256,
        "outcome": "partial",
        "observed_at": "2026-10-09T00:00:00Z",
        "warnings": ["manual_reconciliation_required"],
        "rows": [
            {
                "submission_id": "submission-a",
                "sakai_user_id": "student-a",
                "stage": "unknown",
                "content_revision": "content",
                "grade_revision": "grade",
                "assignment_score": None,
                "grade_released": False,
                "returned": False,
                "gradebook_score": None,
                "reason": "commit_in_progress",
                "retry_action": "human_reconciliation",
            }
        ],
    }

    def handler(r):
        calls.append(r)
        assert r.headers["authorization"] == "Bearer synthetic-token"
        assert r.url.path.endswith("/course-a/assignments/assignment-a/grading-save")
        assert "course_id" not in json.loads(r.content)
        return httpx.Response(200, json=receipt)

    client = SakaiClient(
        settings(assignment_grading_enabled=True),
        FakeOBO(),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    result = asyncio.run(
        client.grading_request("save_assignment_grades", principal(), request)
    )
    assert (
        result.outcome == "partial"
        and result.rows[0].stage == "unknown"
        and len(calls) == 1
    )
    calls.clear()
    client._http = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda r: (calls.append(r), httpx.Response(503))[1]
        )
    )
    with pytest.raises(SakaiError) as error:
        asyncio.run(
            client.grading_request("save_assignment_grades", principal(), request)
        )
    assert error.value.code == ErrorCode.AMBIGUOUS_WRITE_OUTCOME and len(calls) == 1


def test_grading_tool_invocation_validates_and_forwards(monkeypatch):
    import sakai_mcp.grading_tools as tools

    monkeypatch.setattr(tools, "get_access_token", principal)

    class Client(FakeClient):
        async def grading_request(self, name, token, request):
            assert name == "list_assignment_submissions" and request.limit == 50
            return {
                "items": [],
                "next_cursor": None,
                "snapshot_revision": "snapshot",
                "observed_at": "2026-10-09T00:00:00Z",
                "completeness": {"complete": True, "scope": "site", "reasons": []},
                "warnings": [],
            }

    config = settings(assignment_grading_enabled=True)
    server = create_server(config, Client(), EntraTokenVerifier(config, lambda _: None))
    result = asyncio.run(
        server.call_tool(
            "list_assignment_submissions",
            {"course_id": "course-a", "assignment_id": "assignment-a"},
        )
    )
    assert result.is_error is not True


def make_workspace(tmp_path: Path, data: bytes, name="roll.txt"):
    root = tmp_path / "run"
    root.mkdir(mode=0o700)
    raw = root / "submissions" / "raw" / "submission-a"
    raw.mkdir(parents=True)
    (raw / "artifact").write_bytes(data)
    manifest = {
        "course_id": "course-a",
        "assignment_id": "assignment-a",
        "rows": [
            {
                "submission_id": "submission-a",
                "sakai_user_ids": ["student-a"],
                "status": "ready",
                "content_revision": "content",
                "artifact_ids": ["artifact"],
            }
        ],
        "artifacts": [
            {
                "artifact_id": "artifact",
                "original_name": name,
                "raw_path": "submissions/raw/submission-a/artifact",
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        ],
    }
    (root / "manifest.json").write_text(json.dumps(manifest))
    config = {
        "course_id": "course-a",
        "assignment_id": "assignment-a",
        "submission_contract": {
            "file_count": 1,
            "encoding": "utf-8",
            "alphabet": ["A", "B", "C", "D"],
            "answer_count": 5,
            "filename": "<roll-number>.txt",
        },
        "expected_filenames": {"student-a": "roll.txt"},
        "normalization": {
            "uppercase_answers": True,
            "trim_answer_whitespace": True,
            "extension_case": True,
        },
        "grading": {
            "method": "deterministic_mcq",
            "key": ["A", "C", "B", "D", "A"],
            "max_points": "5",
            "per_correct": "1",
            "per_incorrect": "0",
            "negative_marking": False,
        },
        "policies": {"late_penalty": None},
    }
    path = root / "grading-config.json"
    path.write_text(json.dumps(config))
    return root, path


@pytest.mark.parametrize(
    "data,score",
    [
        (b"A\nC\nB\nD\nA\n", "5"),
        (b"A\nC\nA\nD\nA\n", "4"),
        (b"a\nc\nb\nd\na\n", "5"),
        (b" A \n C\nB \nD\nA\n", "5"),
        (b"A\nC\nB\nD\n", None),
        (b"A\nC\nX\nD\nA\n", None),
        (b"", None),
        (b"%PDF-1.7 fake", None),
    ],
)
def test_deterministic_known_cases_preserve_raw(tmp_path, data, score):
    root, config = make_workspace(tmp_path, data)
    result = grade_mcq(root, config)
    assert result[0]["score"] == score
    assert result[0]["review_status"] == (
        "proposed" if score is not None else "review_required"
    )
    assert (root / "submissions/raw/submission-a/artifact").read_bytes() == data
    assert (root / "results/review-required.csv").exists()


def test_integrity_failure_and_git_workspace_are_rejected(tmp_path):
    root, config = make_workspace(tmp_path, b"A\nC\nB\nD\nA\n")
    (root / "submissions/raw/submission-a/artifact").write_bytes(b"changed")
    with pytest.raises(ValueError, match="integrity"):
        grade_mcq(root, config)
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    with pytest.raises(ValueError, match="Git"):
        private_workspace(repo / "grading")


def test_artifact_gateway_requires_token_and_supports_authorized_ranges():
    data = b"abcde"
    sha = hashlib.sha256(data).hexdigest()

    class Verifier:
        async def verify_token(self, token):
            return principal() if token == "trusted" else None

    class Client:
        async def grading_artifact(self, *args):
            return httpx.Response(
                200,
                content=data,
                headers={"content-length": "5", "x-content-sha256": sha},
            )

    app = Starlette(routes=[artifact_route(Client(), Verifier())])

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="https://mcp.example.test"
        ) as http:
            url = "/grading-artifacts/course-a/assignment-a/export/artifact"
            assert (await http.get(url)).status_code == 401
            response = await http.get(
                url, headers={"authorization": "Bearer trusted", "range": "bytes=1-3"}
            )
            assert (
                response.status_code == 206
                and response.content == b"bcd"
                and response.headers["content-range"] == "bytes 1-3/5"
            )
            assert (
                await http.get(
                    url,
                    headers={"authorization": "Bearer trusted", "range": "bytes=100-"},
                )
            ).status_code == 416

    asyncio.run(run())


def test_oversized_feedback_is_rejected_before_network():
    calls = []
    client = SakaiClient(
        settings(assignment_grading_enabled=True),
        FakeOBO(),
        httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda request: calls.append(request) or httpx.Response(200, json={})
            )
        ),
    )
    value = save_request()
    value["grades"][0]["feedback"] = {"action": "replace", "text": "x" * 61_000}
    request = SaveAssignmentGradesRequest.model_validate(value)
    with pytest.raises(SakaiError) as error:
        asyncio.run(
            client.grading_request("save_assignment_grades", principal(), request)
        )
    assert error.value.code == ErrorCode.VALIDATION_ERROR
    assert not calls


def test_workspace_rejects_symlinked_evidence(tmp_path):
    root = tmp_path.resolve() / "private"
    root.mkdir(mode=0o700)
    (root / "raw").symlink_to(tmp_path.resolve(), target_is_directory=True)
    with pytest.raises(ValueError, match="symlinks"):
        private_workspace(root)


def test_read_query_failure_is_not_an_ambiguous_write():
    client = SakaiClient(
        settings(assignment_grading_enabled=True),
        FakeOBO(),
        httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503))),
    )
    request = CONTRACTS["get_assignment_grades"][0](
        course_id="course-a",
        assignment_id="assignment-a",
        rows=[{"submission_id": "submission-a", "sakai_user_id": "student-a"}],
    )
    with pytest.raises(SakaiError) as error:
        asyncio.run(
            client.grading_request("get_assignment_grades", principal(), request)
        )
    assert error.value.code == ErrorCode.DEPENDENCY_UNAVAILABLE


def test_expired_export_maps_to_missing_evidence():
    with pytest.raises(SakaiError) as error:
        SakaiClient._raise_for_status(410, "GET", unsupported=True)
    assert error.value.code == ErrorCode.NOT_FOUND
