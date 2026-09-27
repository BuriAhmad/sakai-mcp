"""Privacy-preserving MCP call audit and correlation context."""

import hashlib
import json
import logging
import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

from mcp.server.auth.middleware.auth_context import get_access_token

_request_id: ContextVar[str | None] = ContextVar("sakai_mcp_request_id", default=None)
_created_ref: ContextVar[str | None] = ContextVar("sakai_mcp_created_ref", default=None)
_audit = logging.getLogger("sakai_mcp.audit")
_OUTCOMES = frozenset({
    "UNAUTHENTICATED", "FORBIDDEN", "NOT_FOUND", "VALIDATION_ERROR", "CONFLICT",
    "RATE_LIMITED", "DEPENDENCY_UNAVAILABLE", "AMBIGUOUS_WRITE_OUTCOME", "INTERNAL_ERROR",
})


def configure_logging(level: str) -> None:
    # HTTPX's standard INFO message includes the full Sakai path and object IDs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    # The SDK's INFO tool-error log may include raw schema-validation inputs.
    logging.getLogger("mcp.server.mcpserver.server").setLevel(logging.WARNING)
    for existing in list(_audit.handlers):
        if existing.name == "sakai_mcp_audit":
            _audit.removeHandler(existing)
    handler = logging.StreamHandler(sys.stdout)
    handler.name = "sakai_mcp_audit"
    handler.setFormatter(logging.Formatter("%(message)s"))
    _audit.addHandler(handler)
    _audit.propagate = False
    _audit.setLevel(getattr(logging, level.upper(), logging.INFO))


def current_request_id() -> str:
    return _request_id.get() or str(uuid4())


def _digest(value: str | None) -> str | None:
    return hashlib.sha256(value.encode()).hexdigest()[:16] if value else None


def record_created(object_id: str) -> None:
    _created_ref.set(_digest(object_id))


@asynccontextmanager
async def audit_call(
    tool: str, classification: str, course_id: str | None = None, target_id: str | None = None
) -> AsyncIterator[None]:
    request_id = str(uuid4())
    context_token = _request_id.set(request_id)
    created_token = _created_ref.set(None)
    access = get_access_token()
    claims = access.claims if access is not None and isinstance(access.claims, dict) else {}
    tenant = claims.get("tid")
    object_id = claims.get("oid")
    actor = _digest(f"{tenant}:{object_id}") if isinstance(tenant, str) and isinstance(object_id, str) else None
    start = monotonic()
    outcome = "OK"
    try:
        yield
    except Exception as exc:
        candidate = str(exc)
        outcome = candidate if candidate in _OUTCOMES else "INTERNAL_ERROR"
        raise
    finally:
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": request_id,
            "actor_ref": actor,
            "tool": tool,
            "classification": classification,
            "course_ref": _digest(course_id),
            "target_ref": _digest(target_id),
            "created_ref": _created_ref.get(),
            "outcome": outcome,
            "latency_ms": round((monotonic() - start) * 1000),
            "revision": os.getenv("CONTAINER_APP_REVISION"),
            "commit": os.getenv("APP_COMMIT"),
        }
        _audit.info(json.dumps(event, separators=(",", ":")))
        _created_ref.reset(created_token)
        _request_id.reset(context_token)
