# Sakai MCP architecture

The implementation plan and phase gates are in [`../MCP_IMPLEMENTATION_RUNBOOK.md`](../MCP_IMPLEMENTATION_RUNBOOK.md). The Sakai 25.2 endpoint choices and their source evidence are in [`../evidence/mcp/phase-3-sakai-api-reconnaissance.md`](../evidence/mcp/phase-3-sakai-api-reconnaissance.md).

V1 is a delegated, user-scoped Streamable HTTP MCP service under `services/mcp/`. It obtains a downstream delegated token for a narrow Sakai integration API, implemented inside tracked `apps/sakai/webapi/`. The Sakai endpoint uses request-local current-user context and ordinary permission-aware services. Azure infrastructure belongs under `deployment/infra/` and uses the established exact-commit deployment and rollback path.

The five V1 operations are own courses, own grades, visible course announcements, authorized course submissions, and announcement creation. Announcement creation is the only write. An unrelated-site announcement leak was observed in Sakai's existing generic WebAPI route, so the MCP route must first verify site visit permission and must not proxy the generic endpoint. Own grades must remain bound to the acting user even when that user can grade others. Submission reads require assignment/site equality and the relevant group or section grade permission.

The Sakai adapter's exact routes, property names, default-disabled filter, and local test command are in [`sakai-adapter.md`](sakai-adapter.md).

The development tenant has issued both audience-specific tokens through certificate-backed OBO. Only the downstream Sakai API token carries `extn.SakaiEid`, as a one-element string array; see [`phase-6-entra-plan.md`](../evidence/mcp/phase-6-entra-plan.md). The MCP service validates its own audience and `mcp.access` scope, exchanges through OBO, and never accepts a caller-selected Sakai identity. The Sakai adapter validates its distinct audience and `sakai.mcp.access` scope, then resolves the verified extension through Sakai 25.2's external trusted evidence path. Client-product compatibility and deployed endpoint behavior are still unverified. No generic Sakai URL proxy is permitted.
