# Phase 4 repository layout (2026-09-26)

Status: **PASS**.

Before adding paths, `rg --files services deployment/infra docs` showed only `services/mcp/README.md` in the MCP service area, existing Bicep under `deployment/infra/`, and no competing MCP package or infrastructure tree. The repository has no established Python application package convention to preserve. The default `services/mcp/src/sakai_mcp/` package was created, with an MCP-specific scoped `AGENTS.md`; tests will be added under `services/mcp/tests/` alongside actual code. Project architecture documentation was added at `docs/mcp/architecture.md`. Sakai integration will live in the existing tracked `apps/sakai/webapi/` module, as Phase 3 determined. No new root-level service, Sakai checkout, patch export, or IaC tree was created.
