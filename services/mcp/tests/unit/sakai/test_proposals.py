"""Proposal reads and private writes have distinct receipts and retry semantics."""

import asyncio
import json

import httpx
import pytest

from sakai_mcp.contracts.grading_proposals import ProposalPayload
from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.client import SakaiClient
from tests.fixtures import grading_data as f
from tests.fixtures.authentication import settings
from tests.fixtures.sakai import FakeOBO, principal


@pytest.mark.parametrize("mutation", [False, True])
@pytest.mark.parametrize("failure", [None, "receipt", "unavailable"])
def test_proposal_transport_preserves_receipt_identity_and_attempt_counts(
    mutation, failure
):
    calls = []
    payload = ProposalPayload(config=f.config(), rows=[])

    def handler(request):
        calls.append(request)
        root = f"/api/mcp/v1/courses/{f.COURSE}/assignments/{f.ASSIGNMENT}/grading-proposals"
        assert request.url.host == "sakai.example.test"
        assert request.method == ("POST" if mutation else "GET")
        assert request.url.path == (root if mutation else root + "/" + f.PROPOSAL)
        if mutation:
            assert json.loads(request.content) == {
                "proposal_id": f.PROPOSAL,
                "export_id": f.EXPORT,
                "payload": payload.model_dump(),
            }
        if failure == "unavailable":
            return httpx.Response(503)
        return httpx.Response(
            200,
            json={
                "proposal_id": "99999999-9999-4999-8999-999999999999"
                if failure == "receipt"
                else f.PROPOSAL,
                "export_id": f.EXPORT,
                "request_sha256": "a" * 64,
                "expires_at": "2026-10-15T00:00:00Z",
                "payload": payload.model_dump(),
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            gateway = SakaiClient(
                settings(assignment_grading_enabled=True), FakeOBO(), http
            ).grading
            if mutation:
                return await gateway.create_proposal(
                    principal(), f.COURSE, f.ASSIGNMENT, f.PROPOSAL, payload, f.EXPORT
                )
            return await gateway.get_proposal(
                principal(), f.COURSE, f.ASSIGNMENT, f.PROPOSAL
            )

    if failure:
        with pytest.raises(SakaiError) as error:
            asyncio.run(run())
        assert error.value.code == (
            ErrorCode.AMBIGUOUS_WRITE_OUTCOME
            if mutation
            else ErrorCode.DEPENDENCY_UNAVAILABLE
            if failure == "unavailable"
            else ErrorCode.INTERNAL_ERROR
        )
    else:
        assert asyncio.run(run()).proposal_id == f.PROPOSAL
    assert len(calls) == (3 if failure == "unavailable" and not mutation else 1)
