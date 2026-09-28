import asyncio
import json
import logging

import pytest
from mcp.server.auth.provider import AccessToken

import sakai_mcp.audit as audit_module
from sakai_mcp.audit import (
    audit_call,
    configure_logging,
    current_request_id,
    record_created,
)


def test_audit_logs_safe_fields_without_identity_or_content(monkeypatch, capsys):
    secret_token = "private-token-example"
    raw_user = "private-user-example"
    raw_course = "private-course-example"
    raw_body = "private-announcement-body-example"
    monkeypatch.setattr(
        audit_module,
        "get_access_token",
        lambda: AccessToken(
            token=secret_token,
            client_id="test",
            scopes=["mcp.access"],
            claims={"tid": "synthetic-tenant", "oid": raw_user},
        ),
    )
    configure_logging("INFO")

    async def run():
        async with audit_call("create_course_announcement", "write", raw_course):
            assert current_request_id()
            record_created("private-created-id")
            _ = raw_body

    asyncio.run(run())
    output = capsys.readouterr().out
    assert all(secret not in output for secret in (secret_token, raw_user, raw_course, raw_body, "private-created-id"))
    event = json.loads(output.strip().splitlines()[-1])
    assert event["tool"] == "create_course_announcement"
    assert event["classification"] == "write"
    assert event["outcome"] == "OK"
    assert event["actor_ref"] and event["course_ref"] and event["created_ref"] and event["request_id"]
    assert logging.getLogger("httpx").level == logging.WARNING


def test_failure_audit_redacts_details_and_resets_request_context(capsys):
    configure_logging("INFO")
    before = current_request_id()

    async def run():
        with pytest.raises(RuntimeError):
            async with audit_call("get_my_grades", "read", "private-course"):
                assert current_request_id() != before
                raise RuntimeError("private bearer and grade body")

    asyncio.run(run())
    assert audit_module._request_id.get() is None
    assert audit_module._created_ref.get() is None
    output = capsys.readouterr().out
    assert "private" not in output and "bearer" not in output
    event = json.loads(output.strip().splitlines()[-1])
    assert event["outcome"] == "INTERNAL_ERROR"
    assert event["request_id"]
