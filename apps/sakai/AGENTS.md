# Sakai application source

The [canonical existing-HTTP migration plan](../../docs/mcp/existing-api-migration/implementation-plan.md) governs current migration work. Historical native business/lock/storage descriptions below document transition dependencies, not authorization to extend or retain them indefinitely. Only delegated authentication/session integration may be added in Sakai; replacement, focused retirement and data preservation follow the plan.

The native shared auth module and filter wiring are intentionally absent from this tool-only source line. See [development-line ownership](../../docs/DEVELOPMENT_WORKTREES.md). Keep existing business migration/retirement here; assemble matching auth only in a separately authorized integration line.

The transitional legacy native MCP integration is grouped under `webapi/src/main/java/org/sakaiproject/webapi/mcp/{security,assessment,contracts,grading}/`. Its [source map](webapi/src/main/java/org/sakaiproject/webapi/mcp/README.md) explains focused grading services and mirrored tests. Preserve their explicit authorization, evidence loading, row-lock boundaries and durable records.

The [MCP-only grading migration](../../docs/SAKAI_GRADING_MCP_RESOURCES.md) replaces the local importer with SDK resources and server proposal/report tools. Native resource/proposal endpoints preserve delegated permissions and existing grading gates; use the [two-stage grading release procedure](../../docs/GRADING_MCP_RESOURCE_RELEASE.md) before deployment.
This directory is the tracked Sakai 25.2 source in the `sakai-mcp` repository. The baseline is upstream commit `b5b7800f0fcddf9d0db47276a66065189365d905`; see `docs/SAKAI_SOURCE.md` for provenance and the deployment boundary.

For opt-in Assignment/Gradebook/Calendar coordination, consult the [assignment setup implementation research](../../docs/SAKAI_ASSIGNMENT_SETUP.md) before changing native services or adapter endpoints.

For opt-in TA grading, read the [grading design](../../docs/SAKAI_ASSIGNMENT_GRADING.md) and [local implementation evidence](../../docs/evidence/mcp/assignment-grading-local.md). The new submission version column requires a reviewed migration before native deployment, even with grading flags disabled.

Consult [the Sakai integration guide](../../docs/SAKAI_INTEGRATION_GUIDE.md) before adding or changing integration endpoints; it maps discovered domain capabilities to native providers, services and tool implementations.

- Keep project changes focused and document why they differ from upstream.
- Do not create a nested Git repository here. Commit Sakai changes through the root `sakai-mcp` repository.
- Follow Sakai's existing Maven/module structure and run focused tests for changed modules.
- Check database and runtime compatibility before changing schema, authentication, or public APIs.
- Treat `/opt/sakai-src` on the VM as a deployed copy; make durable code changes here.
