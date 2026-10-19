"""Authenticated MCP invocation and sanitized error translation."""

from collections.abc import Awaitable, Callable
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, ValidationError

from sakai_mcp.audit import audit_call, record_outcome
from sakai_mcp.errors import ErrorCode, SakaiError


def principal() -> AccessToken:
    token = get_access_token()
    if token is None:
        raise ToolError(ErrorCode.UNAUTHENTICATED.value)
    return token


async def invoke_grading(
    operation: Callable[..., Awaitable[Any]],
    request_type: type[BaseModel],
    arguments: dict[str, Any],
    *,
    write: bool = False,
) -> Any:
    token = principal()
    async with audit_call(
        operation.__name__,
        "write" if write else "read",
        arguments.get("course_id"),
        arguments.get("assignment_id"),
    ):
        try:
            request = request_type.model_validate(arguments)
            result = await operation(token, request)
            if getattr(result, "outcome", None) == "partial":
                record_outcome("PARTIAL_SUCCESS")
            return result
        except ValidationError:
            raise ToolError(ErrorCode.VALIDATION_ERROR.value) from None
        except SakaiError as error:
            raise ToolError(error.code.value) from None
