# MCP service working rules

The [MCP-only grading migration](../../docs/SAKAI_GRADING_MCP_RESOURCES.md) replaces the local importer with SDK resources and server proposal/report tools. Native resource/proposal endpoints preserve delegated permissions and existing grading gates; use the [two-stage grading release procedure](../../docs/GRADING_MCP_RESOURCE_RELEASE.md) before deployment.
The project-owned Python MCP service and its tests belong under this directory. Follow [`docs/MCP_IMPLEMENTATION_RUNBOOK.md`](../../docs/MCP_IMPLEMENTATION_RUNBOOK.md) in phase order and keep its gate statuses and `docs/evidence/mcp/` reports accurate.

The next-phase [assignment setup design](../../docs/SAKAI_ASSIGNMENT_SETUP.md) contains next-phase contracts, source research and implementation gates. The user-authorized implementation is separately gated; it does not widen the default V1 release. See [release evidence](../../docs/evidence/mcp/assignment-setup-release.md) for the enabled development deployment and remaining acceptance limits.

Before implementing a Sakai capability, consult [the Sakai integration guide](../../docs/SAKAI_INTEGRATION_GUIDE.md) for native interfaces and limitations; seeding UI automation is not the production MCP adapter contract.

The [assignment grading design](../../docs/SAKAI_ASSIGNMENT_GRADING.md), [contracts](../../docs/mcp/assignment-grading-contracts.json) and [local evidence](../../docs/evidence/mcp/assignment-grading-local.md) cover the implemented opt-in TA workflow. Preserve the default catalog and independent gates. `ASSIGNMENT_GRADING_ENABLED` and the matching Sakai property remain false by default. Deployment requires the submission version column, private durable storage and separate live acceptance. Do not automatically retry uncertain grading mutations.

- Expose only the five V1 tools by default. `create_course_announcement` is the only V1 write. The three assignment setup tools require explicit `ASSIGNMENT_SETUP_ENABLED`; keep it false for V1 and preserve its regression tests. Enabling the matching Sakai property or deploying remains a separate runtime action.
- Follow the root guide's [approval initiative](../../AGENTS.md#take-initiative-at-approval-boundaries): when the intended workflow requires deploying or enabling implemented tools, prepare the release prerequisites and proactively request any missing authorization. Report separately what exists locally, what the connected endpoint exposes and what has passed acceptance; a Skill or local tool implementation alone does not make a capability available to the client.
- Derive the Sakai acting user from validated delegated identity. Never accept a tool-supplied user ID, token, or destination URL as authority.
- Keep credentials, tokens, test-user identifiers, and sensitive Sakai content out of Git, logs, and evidence. Use synthetic sandbox data for tests.
- Treat ambiguous announcement-create outcomes as unknown; never retry them automatically without the runbook's verified reconciliation mechanism.
- Put Sakai Java changes in tracked `apps/sakai/`, Azure Bicep in `deployment/infra/`, and implementation or operations documentation in `docs/`.
