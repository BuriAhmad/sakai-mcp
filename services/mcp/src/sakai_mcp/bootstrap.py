"""Construct concrete runtime dependencies without import-time credentials."""

import os
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from starlette.applications import Starlette

from sakai_mcp.audit import configure_logging
from sakai_mcp.config import Settings
from sakai_mcp.mcp.http import add_health_routes, canonicalize_resource_metadata
from sakai_mcp.mcp.server import create_server
from sakai_mcp.sakai.client import SakaiClient
from sakai_mcp.security.auth import EntraTokenVerifier
from sakai_mcp.security.obo import CredentialFiles, OBOProvider


def create_app(
    settings: Settings | None = None, credentials: CredentialFiles | None = None
) -> Starlette:
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
    manage_client_lifecycle(app, client)
    return add_health_routes(canonicalize_resource_metadata(app, settings))


def manage_client_lifecycle(app: Starlette, client: SakaiClient) -> None:
    """Keep the SDK lifespan intact and release this app's HTTP resources on exit."""
    sdk_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application: Starlette) -> AsyncIterator[Mapping[str, Any]]:
        try:
            async with sdk_lifespan(application) as state:
                yield state or {}
        finally:
            await client.aclose()

    app.router.lifespan_context = lifespan
