"""Explicit positive readiness probes. Expected capability failures are not fixed by this audit.

Run from services/mcp:
uv run --no-sync pytest ../../docs/mcp/existing-api-migration/attachment_readiness_proof.py -q
These probes are intentionally outside the normal passing regression selection.
"""

from pathlib import Path
from xml.etree import ElementTree as ET

import httpx
import pytest

from sakai_mcp.grading.serialization import digest
from sakai_mcp.sakai.existing_transport import ExistingApiTransport
from sakai_mcp.workflows.resources import read_resource
from tests.fixtures.authentication import settings
from tests.fixtures.five_tool_http import FiveToolHTTP
from tests.fixtures.sakai import FakeOBO, principal

ROOT = Path(__file__).resolve().parents[3]


def test_access_servlet_has_delegated_filter_registration():
    root = ET.parse(
        ROOT / "apps/sakai/access/access-tool/tool/src/webapp/WEB-INF/web.xml"
    ).getroot()
    ns = {"w": root.tag[1:].split("}")[0]}
    names = [
        n.findtext("w:filter-name", namespaces=ns).strip()
        for n in root.findall("w:filter-mapping", ns)
        if (n.findtext("w:servlet-name", namespaces=ns) or "").strip()
        == "sakai.access"
    ]
    assert "mcp.credentials" in names and "mcp.session" in names, names


@pytest.mark.asyncio
async def test_direct_content_method_can_deliver_a_known_plain_file():
    expected = b"A\r\nB\n"
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, content=expected, headers={"content-type": "text/plain"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        transport = ExistingApiTransport(settings(), FakeOBO(), http)
        result = await transport.content(
            principal(), "/content/attachment/course-a/Assignments/opaque/answers.txt"
        )
        assert result.data == expected
        assert calls


@pytest.mark.asyncio
async def test_public_attachment_resource_can_deliver_selected_plain_file():
    wire = FiveToolHTTP()
    wire.assignment["submissions"][0]["submittedAttachments"] = [
        {"ref": "/content/attachment/course-a/Assignments/opaque/answers.txt",
         "name": "answers.txt", "size": 5, "type": "text/plain"}
    ]
    client = wire.client()
    _, assignment, rows = await client.submissions.source(
        principal(), "course-a", "assignment-a"
    )
    from sakai_mcp.contracts.submissions import entry

    revision = entry(rows[0], assignment).content_revision
    key = digest(wire.assignment["submissions"][0]["submittedAttachments"][0]["ref"].encode())
    result = await read_resource(
        client, principal(),
        "sakai://courses/course-a/assignments/assignment-a/submissions/submission-a/files/"
        + key + "?revision=" + revision,
    )
    assert result.data == b"A\nB\n"
