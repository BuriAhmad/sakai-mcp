"""Local health routes and canonical OAuth resource discovery."""

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from sakai_mcp.config import Settings


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
    """Advertise the exact path-based Entra Application ID URI."""

    async def metadata(request: Request) -> Response:
        headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, MCP-Protocol-Version",
            "Cache-Control": "public, max-age=3600",
        }
        if request.method == "OPTIONS":
            return Response(status_code=204, headers=headers)
        resource = settings.mcp_resource_uri
        return JSONResponse(
            {
                "resource": resource,
                "authorization_servers": [str(settings.mcp_issuer)],
                "scopes_supported": [f"{resource}/{settings.mcp_required_scope}"],
                "bearer_methods_supported": ["header"],
            },
            headers=headers,
        )

    path = "/.well-known/oauth-protected-resource/mcp"
    matches = [
        i for i, route in enumerate(app.routes) if getattr(route, "path", None) == path
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "MCP protected-resource metadata route was not registered exactly once"
        )
    app.routes[matches[0]] = Route(path, endpoint=metadata, methods=["GET", "OPTIONS"])
    return app
