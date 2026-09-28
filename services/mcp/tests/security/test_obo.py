import asyncio
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from jwt import PyJWKClientConnectionError

from sakai_mcp.auth import EntraTokenVerifier
from sakai_mcp.obo import (
    ExchangeUnavailable,
    InvalidDownstreamToken,
    InvalidUpstreamToken,
    OBOProvider,
)
from tests.helpers import KEY, TENANT, settings, token


def downstream(object_id: str, eid: object, **changes):
    now = datetime.now(UTC)
    claims = {
        "iss": f"https://sts.windows.net/{TENANT}/",
        "tid": str(TENANT),
        "aud": settings().sakai_audience,
        "oid": object_id,
        "scp": "sakai.mcp.access",
        "extn.SakaiEid": eid,
        "exp": now + timedelta(minutes=20),
        "nbf": now - timedelta(minutes=1),
    }
    claims.update(changes)
    return jwt.encode(claims, KEY, algorithm="RS256")


def provider(exchange):
    config = settings()
    inbound = EntraTokenVerifier(config, lambda _: KEY.public_key())
    return OBOProvider(config, inbound, exchange=exchange, downstream_signing_key=lambda _: KEY.public_key())


def access(object_id: str):
    config = settings()
    inbound = EntraTokenVerifier(config, lambda _: KEY.public_key())
    issued = asyncio.run(inbound.verify_token(token(oid=object_id)))
    assert issued is not None
    return issued


def test_user_a_and_b_obtain_distinct_downstream_identities():
    a = "00000000-0000-0000-0000-000000000001"
    b = "00000000-0000-0000-0000-000000000002"
    seen = []

    def exchange(assertion, scopes):
        seen.append((assertion, scopes))
        object_id = jwt.decode(assertion, options={"verify_signature": False})["oid"]
        return {"access_token": downstream(object_id, ["synthetic-" + object_id[-1]])}

    obo = provider(exchange)
    result_a = asyncio.run(obo.acquire(access(a)))
    result_b = asyncio.run(obo.acquire(access(b)))
    assert result_a.object_id == a and result_a.sakai_eid == "synthetic-1"
    assert result_b.object_id == b and result_b.sakai_eid == "synthetic-2"
    assert seen[0][0] != seen[1][0]
    assert seen[0][1] == [f"{settings().sakai_audience}/sakai.mcp.access"]


def test_wrong_upstream_audience_cannot_reach_exchange():
    called = False

    def exchange(*_):
        nonlocal called
        called = True
        return {}

    upstream = access("00000000-0000-0000-0000-000000000001")
    upstream.resource = "api://wrong"
    with pytest.raises(InvalidUpstreamToken):
        asyncio.run(provider(exchange).acquire(upstream))
    assert not called


def test_missing_consent_fails_without_exposing_response():
    with pytest.raises(ExchangeUnavailable, match="did not issue") as error:
        asyncio.run(provider(lambda *_: {"error": "sensitive token endpoint detail"}).acquire(
            access("00000000-0000-0000-0000-000000000001")
        ))
    assert "sensitive" not in str(error.value)


def test_downstream_jwks_outage_is_dependency_failure_and_recovers():
    a = "00000000-0000-0000-0000-000000000001"
    healthy = False

    def signing_key(_):
        if not healthy:
            raise PyJWKClientConnectionError("synthetic private JWKS detail")
        return KEY.public_key()

    config = settings()
    inbound = EntraTokenVerifier(config, lambda _: KEY.public_key())
    obo = OBOProvider(
        config, inbound,
        exchange=lambda *_: {"access_token": downstream(a, ["synthetic-1"])},
        downstream_signing_key=signing_key,
    )
    with pytest.raises(ExchangeUnavailable) as error:
        asyncio.run(obo.acquire(access(a)))
    assert "private" not in str(error.value)
    healthy = True
    assert asyncio.run(obo.acquire(access(a))).object_id == a


@pytest.mark.parametrize(
    "changes",
    [
        {"aud": "api://wrong"},
        {"scp": "other.scope"},
        {"tid": "00000000-0000-0000-0000-000000000000"},
        {"oid": "00000000-0000-0000-0000-000000000099"},
        {"extn.SakaiEid": []},
        {"extn.SakaiEid": ["one", "two"]},
        {"extn.SakaiEid": [123]},
        {"extn.SakaiEid": ["  "]},
        {"extn.SakaiEid": None},
    ],
)
def test_downstream_identity_and_claim_shape_fail_closed(changes):
    a = "00000000-0000-0000-0000-000000000001"
    invalid = downstream(a, ["synthetic-1"], **changes)
    with pytest.raises(InvalidDownstreamToken):
        asyncio.run(provider(lambda *_: {"access_token": invalid}).acquire(access(a)))
