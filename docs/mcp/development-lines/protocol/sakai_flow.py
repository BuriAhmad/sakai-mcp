"""Private per-invocation native conversation state; never a public credential."""

import asyncio
import secrets
import time
from dataclasses import dataclass, field

from sakai_mcp.errors import ErrorCode, SakaiError


@dataclass(repr=False)
class SakaiFlow:
    nonce: str = field(default_factory=lambda: secrets.token_hex(32), repr=False)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    created: float = field(default_factory=time.monotonic, repr=False)
    steps: int = 0
    started: bool = False
    closed: bool = False
    cleanup_failed: bool = False

    def next_step(self) -> None:
        if self.closed or self.steps >= 50 or time.monotonic() - self.created >= 120:
            raise SakaiError(ErrorCode.CONFLICT)
        self.steps += 1

    def headers(self, *, end: bool = False) -> dict[str, str]:
        return {"X-MCP-Flow": self.nonce, **({"X-MCP-Flow-End": "1"} if end else {})}
