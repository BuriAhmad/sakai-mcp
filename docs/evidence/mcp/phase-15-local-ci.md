# Phase 15 — MCP local and CI validation (2026-09-27)

Status: **IN PROGRESS; local suite PASS; first GitHub MCP job NOT RUN**.

The repository's existing validation workflow now has an MCP Python job using the officially documented pinned `astral-sh/setup-uv` action and a fixed uv version, Python 3.11, `uv sync --locked`, pytest, Ruff, and mypy. It has no Azure credentials and does not call the live Sakai sandbox. Local tests are organized under `services/mcp/tests/unit/`, `integration/`, `protocol/`, and `security/`. A composed synthetic integration test exercises JWT verification, per-user OBO, fixed-host Sakai HTTP, and authenticated MCP calls with in-memory transports. The live synthetic-user smoke is intentionally kept in ignored local artifacts and is not an ordinary CI job.

Local result: **39 tests PASS**, Ruff PASS, mypy PASS, Actionlint PASS, and `uv sync --locked` PASS. Tests include invalid audience/issuer/scope, two-user token separation, fixed Sakai host, read retry, no blind create retry, five tool schemas and annotations, server-derived identity, static catalog plus manual student privileged-call denial, structured outputs, log redaction, and no elicitation path. The static catalog limitation is documented in Phase 12; authorization remains enforced on every call. GitHub execution evidence is pending the next push.
