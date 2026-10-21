"""Real SDK client protocol coverage; production has no grading MCP client."""

import asyncio
import base64
import json
from pathlib import Path

import httpx
import httpx2
import pytest
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
from mcp.types import BlobResourceContents, ResourceLink, TextResourceContents

from sakai_mcp.contracts import grading_native as gm
from sakai_mcp.contracts import grading_proposals as proposals
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.grading.serialization import digest, payload_hash
from sakai_mcp.mcp.server import create_server
from sakai_mcp.sakai.client import SakaiClient
from sakai_mcp.workflows.resources import parse_uri, resource_root
from tests.fixtures import grading_data as f
from tests.fixtures.authentication import settings
from tests.fixtures.sakai import FakeClient, FakeOBO, principal


class GradingClient(FakeClient):
    def __init__(self, data=f.DATA, mime="text/plain"):
        super().__init__()
        self.data, self.mime, self.record = data, mime, None
        self.downloads = self.private_writes = 0
        self.revoked = False
        self.validated = []

    async def _response(self, name, token, request):
        if self.revoked:
            raise SakaiError(ErrorCode.FORBIDDEN)
        if name in {"save_assignment_grades", "release_assignment_grades"}:
            assert request.mode == "validate"
            kind = "save" if name == "save_assignment_grades" else "release"
            assert request.payload_sha256 == payload_hash(
                kind,
                f.COURSE,
                f.ASSIGNMENT,
                "config",
                [r.model_dump() for r in request.grades],
            )
            self.validated.append(request)
            return gm.OperationReceipt(
                operation_id=request.operation_id,
                kind=kind,
                mode="validate",
                payload_sha256=request.payload_sha256,
                outcome="validated",
                observed_at="now",
                rows=[],
                warnings=[],
            )
        return {
            "get_assignment_grading_context": f.context(),
            "list_assignment_submissions": f.roster(),
            "get_assignment_submission": gm.GetAssignmentSubmissionResult(
                submission=f.submission(),
                inline_text="<p>Untrusted</p>",
                inline_content_type="text/html",
                feedback_comment=None,
                feedback_sha256=None,
                observed_at="now",
                warnings=[],
            ),
            "get_assignment_submission_export": f.manifest(self.data, self.mime),
        }[name]

    async def get_assignment_grading_context(self, token, request):
        return await self._response("get_assignment_grading_context", token, request)

    async def list_assignment_submissions(self, token, request):
        return await self._response("list_assignment_submissions", token, request)

    async def get_assignment_submission(self, token, request):
        return await self._response("get_assignment_submission", token, request)

    async def get_assignment_submission_export(self, token, request):
        return await self._response("get_assignment_submission_export", token, request)

    async def save_assignment_grades(self, token, request):
        return await self._response("save_assignment_grades", token, request)

    async def release_assignment_grades(self, token, request):
        return await self._response("release_assignment_grades", token, request)

    async def read_grading_artifact(self, *args):
        if self.revoked:
            raise SakaiError(ErrorCode.FORBIDDEN)
        self.downloads += 1
        return self.data, self.mime, digest(self.data)

    async def read_grading_file(
        self, token, course, assignment, submission, file, revision
    ):
        if self.revoked:
            raise SakaiError(ErrorCode.FORBIDDEN)
        if revision != "content":
            raise SakaiError(ErrorCode.CONFLICT)
        return self.data, self.mime, digest(self.data)

    async def get_proposal(self, token, course, assignment, proposal):
        return await self._proposal_record(token, course, assignment, proposal)

    async def create_proposal(
        self, token, course, assignment, proposal, payload, export
    ):
        return await self._proposal_record(
            token, course, assignment, proposal, payload.model_dump(), export
        )

    async def _proposal_record(
        self, token, course, assignment, proposal, payload=None, export=None
    ):
        if self.revoked:
            raise SakaiError(ErrorCode.FORBIDDEN)
        if payload is not None:
            self.private_writes += 1
            self.record = proposals.ProposalRecord(
                proposal_id=proposal,
                export_id=export,
                request_sha256="b" * 64,
                expires_at="2026-10-15T00:00:00Z",
                payload=proposals.ProposalPayload.model_validate(payload),
            )
        if self.record is None:
            raise SakaiError(ErrorCode.NOT_FOUND)
        return self.record


class Verifier:
    async def verify_token(self, token):
        return principal() if token == "synthetic" else None


@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
@pytest.mark.parametrize(
    "data,mime",
    [
        (f.DATA, "text/plain"),
        (b"%PDF-1.7\x00\xff", "application/pdf"),
        (b"PK\x03\x04\x00\xff", "application/zip"),
        (b"\xff\xfe", "text/plain"),
        (b"\xef\xbb\xbfhello\r\n", "text/plain"),
    ],
)
def test_authenticated_sdk_resource_roundtrip(mode, data, mime):
    backend = GradingClient(data, mime)
    server = create_server(
        settings(assignment_grading_enabled=True), backend, Verifier()
    )
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, host="mcp.example.test"
    )

    async def run():
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
                headers={"Authorization": "Bearer synthetic"},
            ) as http,
            Client(
                streamable_http_client(
                    "https://mcp.example.test/mcp", http_client=http
                ),
                mode=mode,
            ) as host,
        ):
            templates = await host.list_resource_templates()
            assert len(templates.resource_templates) == 5
            result = await host.call_tool(
                "get_assignment_submission_export",
                {
                    "course_id": f.COURSE,
                    "assignment_id": f.ASSIGNMENT,
                    "export_id": f.EXPORT,
                },
            )
            links = [x for x in result.content if isinstance(x, ResourceLink)]
            assert len(links) == 1 and links[0].size == len(data)
            assert "download_path" not in str(result.structured_content)
            resource = await host.read_resource(links[0].uri)
            item = resource.contents[0]
            raw = (
                base64.b64decode(item.blob)
                if isinstance(item, BlobResourceContents)
                else item.text.encode()
            )
            assert raw == data and item.mime_type == mime
            assert item.meta["app.smartdigest.sakai"]["sha256"] == digest(data)
            backend.revoked = True
            with pytest.raises(MCPError, match="FORBIDDEN"):
                await host.read_resource(links[0].uri, cache_mode="bypass")

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
def test_legacy_proposal_read_and_explicit_payload_tools_only_host(mode):
    backend = GradingClient()
    server = create_server(
        settings(assignment_grading_enabled=True), backend, Verifier()
    )
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, host="mcp.example.test"
    )

    async def run():
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
                headers={"Authorization": "Bearer synthetic"},
            ) as http,
            Client(
                streamable_http_client(
                    "https://mcp.example.test/mcp", http_client=http
                ),
                mode=mode,
            ) as host,
        ):
            assert "prepare_assignment_mcq_grades" not in {
                t.name for t in (await host.list_tools()).tools
            }
            # Existing immutable record, not newly generated assessment.
            backend.record = proposals.ProposalRecord(
                proposal_id=f.PROPOSAL,
                export_id=f.EXPORT,
                request_sha256="b" * 64,
                expires_at="2026-10-15T00:00:00Z",
                payload=proposals.ProposalPayload(
                    config=f.config(),
                    rows=[
                        proposals.ProposalRow.model_validate(
                            json.loads(
                                (
                                    Path(__file__).parents[1] / "contracts/grading.json"
                                ).read_text()
                            )["rows"][0]
                        )
                    ],
                ),
            )
            page = await host.call_tool(
                "get_assignment_grading_proposal",
                {
                    "course_id": f.COURSE,
                    "assignment_id": f.ASSIGNMENT,
                    "proposal_id": f.PROPOSAL,
                },
            )
            assert page.structured_content["rows"][0]["score"] == "5"
            uri = (
                resource_root(f.COURSE, f.ASSIGNMENT)
                + f"/proposals/{f.PROPOSAL}/reports/marks"
            )
            report = await host.read_resource(uri)
            assert (
                isinstance(report.contents[0], TextResourceContents)
                and "student-a,5" in report.contents[0].text
            )
            fallback = await host.call_tool(
                "read_assignment_grading_resource", {"uri": uri}
            )
            assert (
                not fallback.is_error
                and fallback.content[0].resource.text == report.contents[0].text
            )
            assert backend.writes == 0
            grade_row = {
                "submission_id": f.SUBMISSION,
                "sakai_user_id": "student-a",
                "expected_content_revision": "content",
                "expected_grade_revision": "grade",
                "score": "5",
                "feedback": {"action": "preserve", "text": None},
            }
            payload = await host.call_tool(
                "prepare_assignment_grade_payload",
                {
                    "course_id": f.COURSE,
                    "assignment_id": f.ASSIGNMENT,
                    "kind": "save",
                    "operation_id": f.PROPOSAL,
                    "expected_assignment_revision": "config",
                    "grades": [grade_row],
                },
            )
            assert not payload.is_error, payload
            assert payload.structured_content["commit_arguments"]["mode"] == "commit"
            assert (
                payload.structured_content["validation"]["outcome"] == "validated"
                and len(backend.validated) == 1
            )
            assert backend.writes == 0
            assert backend.private_writes == 0

    asyncio.run(run())


@pytest.mark.parametrize(
    "uri",
    [
        "https://evil.test/file",
        "sakai://courses/a/assignments/b/submissions/%2e%2e/files/c",
        "sakai://courses/a/assignments/b/files/c?revision=a&revision=b",
        "sakai://courses/a/assignments/b/files/c?token=secret",
        "sakai://courses/a/assignments/b/files/%2fetc%2fpasswd?revision=a",
    ],
)
def test_resource_uri_rejects_arbitrary_urls_paths_and_credentials(uri):
    with pytest.raises(SakaiError):
        parse_uri(uri)


def test_byte_adapter_verifies_stream_and_closes_it():
    def handler(request):
        assert request.headers["authorization"] == "Bearer synthetic-token"
        return httpx.Response(
            200,
            content=b"wrong",
            headers={
                "content-length": "5",
                "x-content-sha256": digest(b"right"),
                "content-type": "text/plain",
            },
        )

    client = SakaiClient(
        settings(assignment_grading_enabled=True),
        FakeOBO(),
        httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(SakaiError) as error:
        asyncio.run(
            client.transport.read_bytes(
                principal(), "/synthetic-byte-transport-fixture"
            )
        )
    assert error.value.code == ErrorCode.CONFLICT


def test_no_helper_client_or_public_download_route():
    source = Path(__file__).parents[2] / "src" / "sakai_mcp"
    assert (
        not (source / "grading_workspace.py").exists()
        and not (source / "grading_artifacts.py").exists()
    )
    for file in source.glob("grading_*.py"):
        text = file.read_text()
        assert (
            "PublicClientApplication" not in text
            and "acquire_token_interactive" not in text
            and "MCP-Protocol-Version" not in text
        )
    server = create_server(settings(), GradingClient(), Verifier())
    assert asyncio.run(server.list_resource_templates()) == []
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, host="mcp.example.test"
    )
    assert all(
        "grading-artifacts" not in str(getattr(route, "path", ""))
        for route in app.routes
    )
