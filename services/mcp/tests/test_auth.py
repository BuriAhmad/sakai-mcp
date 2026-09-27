import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from sakai_mcp.auth import EntraTokenVerifier
from sakai_mcp.config import Settings

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TENANT = UUID("11111111-1111-4111-8111-111111111111")
RESOURCE = "api://22222222-2222-4222-8222-222222222222"


def settings(**changes):
    values = {
        "mcp_public_url": "https://mcp.example.test/mcp",
        "sakai_base_url": "https://sakai.example.test",
        "entra_tenant_id": TENANT,
        "mcp_resource_client_id": UUID("22222222-2222-4222-8222-222222222222"),
        "mcp_issuer": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "mcp_audience": RESOURCE,
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
        "aud": RESOURCE,
        "oid": "00000000-0000-0000-0000-000000000001",
        "azp": "00000000-0000-0000-0000-000000000002",
        "scp": "mcp.access",
        "exp": now + timedelta(minutes=20),
        "nbf": now - timedelta(minutes=1),
    }
    claims.update(changes)
    return jwt.encode(claims, KEY, algorithm="RS256")


def verifier():
    return EntraTokenVerifier(settings(), lambda _: KEY.public_key())


def test_valid_delegated_token_has_verified_principal_without_invented_eid():
    result = asyncio.run(verifier().verify_token(token()))
    assert result is not None
    assert result.subject == f"{TENANT}:00000000-0000-0000-0000-000000000001"
    assert result.scopes == ["mcp.access"]
    assert result.claims == {"tid": str(TENANT), "oid": "00000000-0000-0000-0000-000000000001"}


def test_missing_and_malformed_tokens_fail_closed():
    assert verifier().verify("") is None
    assert verifier().verify("not-a-jwt") is None


def test_signature_and_claim_negatives():
    now = datetime.now(UTC)
    wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    bad_signature = jwt.encode(jwt.decode(token(), options={"verify_signature": False}), wrong_key, algorithm="RS256")
    candidates = [
        bad_signature,
        token(exp=now - timedelta(minutes=2)),
        token(nbf=now + timedelta(minutes=2)),
        token(iss="https://login.microsoftonline.com/other/v2.0"),
        token(tid="00000000-0000-0000-0000-000000000000"),
        token(aud="api://other"),
        token(scp="other.scope"),
        token(oid=""),
        token(oid=None),
        token(scp=None),
        token(azp="", appid=""),
        token(scp=None, roles=["admin"]),
    ]
    assert all(verifier().verify(candidate) is None for candidate in candidates)


def test_wrong_algorithm_and_key_source_fail_closed():
    assert verifier().verify(jwt.encode({"aud": RESOURCE}, "a" * 32, algorithm="HS256")) is None

    def unavailable(_: str):
        raise OSError("JWKS unavailable")

    assert EntraTokenVerifier(settings(), unavailable).verify(token()) is None


def test_configuration_rejects_insecure_urls_and_invalid_audience():
    with pytest.raises(ValidationError):
        settings(sakai_base_url="http://sakai.example.test")
    with pytest.raises(ValidationError):
        settings(mcp_jwks_uri="http://keys.example.test/jwks")
    with pytest.raises(ValidationError):
        settings(mcp_audience="https://unrelated.example.test")
    with pytest.raises(ValidationError):
        settings(sakai_base_url="https://sakai.example.test/other")
