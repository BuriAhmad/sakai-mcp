"""Stable Uvicorn factory entrypoint; construction lives in bootstrap."""

from sakai_mcp.bootstrap import create_app

__all__ = ["create_app"]
