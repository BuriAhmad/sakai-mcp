"""Construct the authenticated SDK server and register its public interface."""

from importlib.metadata import version

from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from pydantic import AnyHttpUrl

from sakai_mcp.config import Settings
from sakai_mcp.mcp.resources import SakaiResourceServer
from sakai_mcp.mcp.tools import register_tools
from sakai_mcp.sakai.client import SakaiClient


def create_server(
    settings: Settings, client: SakaiClient, verifier: TokenVerifier
) -> MCPServer:
    server = SakaiResourceServer(
        grading_client=client,
        grading_enabled=settings.assignment_grading_enabled,
        name="Sakai MCP",
        version=version("sakai-mcp"),
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(str(settings.mcp_issuer)),
            resource_server_url=AnyHttpUrl(settings.mcp_resource_uri),
            required_scopes=[settings.mcp_required_scope],
            validate_token_resource=False,  # The v2 GUID aud and HTTPS resource URI are verified separately.
        ),
    )

    register_tools(server, settings, client)
    return server
