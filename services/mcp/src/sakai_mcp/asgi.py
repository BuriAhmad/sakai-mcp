"""ASGI entrypoint; credentials are supplied as mounted runtime files."""

import os
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from sakai_mcp.audit import configure_logging
from sakai_mcp.auth import EntraTokenVerifier
from sakai_mcp.config import Settings
from sakai_mcp.obo import CredentialFiles, OBOProvider
from sakai_mcp.sakai_client import SakaiClient
from sakai_mcp.server import create_server


async def _live(_: Request) -> JSONResponse:
    return JSONResponse({"status": "live"})


async def _ready(_: Request) -> JSONResponse:
    # Config and credential files are validated while constructing the app.
    # Do not restart replicas during a transient Entra or Sakai outage.
    return JSONResponse({"status": "ready"})


def add_health_routes(app: Starlette) -> Starlette:
    app.add_route("/live", _live, methods=["GET"])
    app.add_route("/ready", _ready, methods=["GET"])
    return app


def canonicalize_resource_metadata(app: Starlette, settings: Settings) -> Starlette:
    """Keep the RFC 9728 resource URI in its interoperable no-trailing-slash form."""

    async def metadata(request: Request) -> Response:
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, MCP-Protocol-Version",
            "Cache-Control": "public, max-age=3600",
        }
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=headers)
        return JSONResponse(
            {
                "resource": settings.mcp_audience,
                "authorization_servers": [str(settings.mcp_issuer)],
                "scopes_supported": [settings.mcp_required_scope],
                "bearer_methods_supported": ["header"],
            },
            headers=headers,
        )

    path = "/.well-known/oauth-protected-resource"
    matches = [i for i, route in enumerate(app.routes) if getattr(route, "path", None) == path]
    if len(matches) != 1:
        raise RuntimeError("MCP protected-resource metadata route was not registered exactly once")
    app.routes[matches[0]] = Route(path, endpoint=metadata, methods=["GET", "OPTIONS"])
    return app


def create_app(settings: Settings | None = None, credentials: CredentialFiles | None = None) -> Starlette:
    settings = settings or Settings()  # type: ignore[call-arg]
    credentials = credentials or CredentialFiles(
        private_key=Path(os.environ["OBO_PRIVATE_KEY_FILE"]),
        certificate=Path(os.environ["OBO_CERTIFICATE_FILE"]),
    )
    verifier = EntraTokenVerifier(settings)
    obo = OBOProvider(settings, verifier, credentials)
    client = SakaiClient(settings, obo)
    server = create_server(settings, client, verifier)
    configure_logging(settings.log_level)
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        max_request_body_size=65_536,
        host=str(settings.mcp_public_url.host),
    )
    return add_health_routes(canonicalize_resource_metadata(app, settings))
