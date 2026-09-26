# MCP service

This directory contains the project-owned MCP service package under `src/sakai_mcp/`. Its implementation and tests are being added in runbook order. Follow the scoped [`AGENTS.md`](AGENTS.md) for security and layout rules.

Dependencies are pinned in [`pyproject.toml`](pyproject.toml) and [`uv.lock`](uv.lock). For local development, run `uv sync --locked` here. The selected SDK is MCP Python 2.2.0. The development Entra token shape and OBO exchange are verified; the Sakai adapter and MCP server are still under implementation, so the service is not runnable yet.

Do not place upstream Sakai source here. The implementation plan, architecture constraints, phase gates, and acceptance criteria are in [`docs/MCP_IMPLEMENTATION_RUNBOOK.md`](../../docs/MCP_IMPLEMENTATION_RUNBOOK.md). Consult and update that runbook as implementation decisions are verified or the plan changes.
