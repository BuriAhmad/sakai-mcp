"""SDK resource integration with per-file MIME metadata and normal delegated auth."""

from collections.abc import Iterable

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.context import Context
from mcp.shared.exceptions import MCPError
from mcp.types import ResourceTemplate
from pydantic import AnyUrl

from sakai_mcp.audit import audit_call
from sakai_mcp.grading_resources import parse_uri, read_resource, resource_templates
from sakai_mcp.sakai_client import ErrorCode, SakaiClient, SakaiError


class SakaiResourceServer(MCPServer):
    grading_client: SakaiClient
    grading_enabled: bool = False

    async def list_resource_templates(self) -> list[ResourceTemplate]:
        return resource_templates() if self.grading_enabled else []

    async def read_resource(
        self, uri: AnyUrl | str, context: Context | None = None
    ) -> Iterable[ReadResourceContents]:
        try:
            if not self.grading_enabled:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
            principal = get_access_token()
            if principal is None:
                raise SakaiError(ErrorCode.UNAUTHENTICATED)
            course, assignment, _, _ = parse_uri(str(uri))
            async with audit_call("resources/read", "read", course, assignment):
                item: ReadResourceContents = await read_resource(
                    self.grading_client, principal, str(uri)
                )
                return [item]
        except SakaiError as error:
            # Use SDK errors without raw URLs, paths, or student content in logs/errors.
            code = (
                -32602
                if error.code == ErrorCode.VALIDATION_ERROR
                else -32002
                if error.code == ErrorCode.NOT_FOUND
                else -32603
            )
            raise MCPError(code=code, message=error.code.value) from None
