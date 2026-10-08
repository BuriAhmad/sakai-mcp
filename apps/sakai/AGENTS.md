# Sakai application source

This directory is the tracked Sakai 25.2 source in the `sakai-mcp` repository. The baseline is upstream commit `b5b7800f0fcddf9d0db47276a66065189365d905`; see `docs/SAKAI_SOURCE.md` for provenance and the deployment boundary.

For opt-in Assignment/Gradebook/Calendar coordination, consult the [assignment setup implementation research](../../docs/SAKAI_ASSIGNMENT_SETUP.md) before changing native services or adapter endpoints.

Consult [the Sakai integration guide](../../docs/SAKAI_INTEGRATION_GUIDE.md) before adding or changing integration endpoints; it maps discovered domain capabilities to native providers, services and tool implementations.

- Keep project changes focused and document why they differ from upstream.
- Do not create a nested Git repository here. Commit Sakai changes through the root `sakai-mcp` repository.
- Follow Sakai's existing Maven/module structure and run focused tests for changed modules.
- Check database and runtime compatibility before changing schema, authentication, or public APIs.
- Treat `/opt/sakai-src` on the VM as a deployed copy; make durable code changes here.
