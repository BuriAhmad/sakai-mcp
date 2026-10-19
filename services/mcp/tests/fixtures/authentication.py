"""Synthetic settings and ephemeral signing key shared by local tests."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from sakai_mcp.config import Settings

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TENANT = UUID("11111111-1111-4111-8111-111111111111")
RESOURCE = "https://mcp.example.test"
MCP_CLIENT_ID = UUID("22222222-2222-4222-8222-222222222222")


def settings(**changes):
    values = {
        "mcp_public_url": RESOURCE,
        "sakai_base_url": "https://sakai.example.test",
        "entra_tenant_id": TENANT,
        "mcp_resource_client_id": MCP_CLIENT_ID,
        "mcp_issuer": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "mcp_audience": str(MCP_CLIENT_ID),
        "sakai_issuer": f"https://sts.windows.net/{TENANT}/",
        "mcp_jwks_uri": f"https://login.microsoftonline.com/{TENANT}/discovery/v2.0/keys",
        "sakai_resource_client_id": UUID("33333333-3333-4333-8333-333333333333"),
        "sakai_audience": "api://33333333-3333-4333-8333-333333333333",
    }
    values.update(changes)
    return Settings(**values)


def token(**changes):
    now = datetime.now(UTC)
    claims = {
        "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "tid": str(TENANT),
        "aud": str(MCP_CLIENT_ID),
        "oid": "00000000-0000-0000-0000-000000000001",
        "azp": "00000000-0000-0000-0000-000000000002",
        "scp": "mcp.access",
        "exp": now + timedelta(minutes=20),
        "nbf": now - timedelta(minutes=1),
    }
    claims.update(changes)
    return jwt.encode(claims, KEY, algorithm="RS256")
