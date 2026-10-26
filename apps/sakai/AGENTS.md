# Sakai application source

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

## Authentication module and feature ownership

The shared `mcp-auth/` module owns delegated identity/session integration; follow
its scoped guide. Follow the root [Git workflow](../../docs/GIT_WORKFLOW.md) for
feature development and main integration. Existing development checkouts retain
[their documented ownership](../../docs/DEVELOPMENT_WORKTREES.md); main assembles
reviewed features rather than inheriting a permanent auth-only development role.

New MCP business capabilities use existing Sakai APIs. Separately authorized
business-interface retirement belongs on its feature branch under the approved
migration/preservation plan. Preserve the shared authentication boundary and
native permissions; this guide does not authorize new native business endpoints,
core changes, data removal or feature activation.
