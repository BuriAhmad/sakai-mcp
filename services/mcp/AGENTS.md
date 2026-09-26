# MCP service working rules

The project-owned Python MCP service and its tests belong under this directory. Follow [`docs/MCP_IMPLEMENTATION_RUNBOOK.md`](../../docs/MCP_IMPLEMENTATION_RUNBOOK.md) in phase order and keep its gate statuses and `docs/evidence/mcp/` reports accurate.

- Expose only the five V1 tools in the runbook. `create_course_announcement` is the only V1 write.
- Derive the Sakai acting user from validated delegated identity. Never accept a tool-supplied user ID, token, or destination URL as authority.
- Keep credentials, tokens, test-user identifiers, and sensitive Sakai content out of Git, logs, and evidence. Use synthetic sandbox data for tests.
- Treat ambiguous announcement-create outcomes as unknown; never retry them automatically without the runbook's verified reconciliation mechanism.
- Put Sakai Java changes in tracked `apps/sakai/`, Azure Bicep in `deployment/infra/`, and implementation or operations documentation in `docs/`.
