# MCP service working rules

The project-owned Python MCP service and its tests belong under this directory. Follow [`docs/MCP_IMPLEMENTATION_RUNBOOK.md`](../../docs/MCP_IMPLEMENTATION_RUNBOOK.md) in phase order and keep its gate statuses and `docs/evidence/mcp/` reports accurate.

The next-phase [assignment setup design](../../docs/SAKAI_ASSIGNMENT_SETUP.md) contains next-phase contracts, source research and implementation gates. The user-authorized local implementation is separately gated; it does not widen the default V1 release.

Before implementing a Sakai capability, consult [the Sakai integration guide](../../docs/SAKAI_INTEGRATION_GUIDE.md) for native interfaces and limitations; seeding UI automation is not the production MCP adapter contract.

- Expose only the five V1 tools by default. `create_course_announcement` is the only V1 write. The three assignment setup tools require explicit `ASSIGNMENT_SETUP_ENABLED`; keep it false for V1 and preserve its regression tests. Enabling the matching Sakai property or deploying remains a separate runtime action.
- Derive the Sakai acting user from validated delegated identity. Never accept a tool-supplied user ID, token, or destination URL as authority.
- Keep credentials, tokens, test-user identifiers, and sensitive Sakai content out of Git, logs, and evidence. Use synthetic sandbox data for tests.
- Treat ambiguous announcement-create outcomes as unknown; never retry them automatically without the runbook's verified reconciliation mechanism.
- Put Sakai Java changes in tracked `apps/sakai/`, Azure Bicep in `deployment/infra/`, and implementation or operations documentation in `docs/`.
