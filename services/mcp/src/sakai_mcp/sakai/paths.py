"""Validate and encode identifiers for fixed Sakai API paths."""

from urllib.parse import quote

from sakai_mcp.errors import ErrorCode, SakaiError


def segment(value: str) -> str:
    if (
        not value
        or value in (".", "..")
        or len(value) > 128
        or value != value.strip()
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise SakaiError(ErrorCode.VALIDATION_ERROR)
    return quote(value, safe="")
