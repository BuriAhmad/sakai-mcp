"""Native stream characterization does not authorize an unaccepted content route."""

import httpx
import pytest

from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.sakai.existing_transport import ExistingApiTransport
from sakai_mcp.workflows.resources import read_resource
from tests.fixtures.authentication import settings
from tests.fixtures.five_tool_http import FiveToolHTTP
from tests.fixtures.sakai import FakeOBO, principal


@pytest.mark.asyncio
async def test_content_method_gate_precedes_obo_or_http():
    obo = FakeOBO()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: pytest.fail("unaccepted HTTP"))
    ) as http:
        transport = ExistingApiTransport(settings(), obo, http)
        with pytest.raises(SakaiError) as error:
            await transport.content(
                principal(), "/content/attachment/course-a/Assignments/answers.txt"
            )
        assert error.value.code == ErrorCode.UNSUPPORTED_CAPABILITY
        assert obo.calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "suffix", ["/submissions/submission-a/files/attachment-a", "/files/attachment-a"]
)
async def test_actual_resource_facade_keeps_attachment_gate(suffix):
    wire = FiveToolHTTP()
    client = wire.client()
    with pytest.raises(SakaiError) as error:
        await read_resource(
            client,
            principal(),
            "sakai://courses/course-a/assignments/assignment-a"
            + suffix
            + "?revision=observed-revision",
        )
    assert error.value.code == ErrorCode.UNSUPPORTED_CAPABILITY
    assert not wire.calls
