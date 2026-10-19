# Local MCP restructuring verification — 15 October 2026

## Scope and source identity

The working-tree change restructures the Python MCP service, project-owned WebAPI integration, related tests, CLI helpers, CI validation and contributor documentation. The starting tracked revision was `208d69ac`; pre-existing user edits were retained. This record describes local source verification, not a deployed revision or new client acceptance result.

The public tool definitions are consolidated in `services/mcp/src/sakai_mcp/mcp/tools.py`. Authentication/OBO, configuration, audit, validation, native transport, workflow coordination and pure grading retain distinct ownership. The runtime imports no Skills. See [the source map](../../../services/mcp/README.md), [architecture](../../mcp/architecture.md) and [the implementation plan](../../mcp/restructuring-plan.md).

## Structural changes

- Replaced the mixed root-level server/client/grading modules with `mcp/`, `security/`, `contracts/`, `sakai/`, `workflows/` and `grading/` packages. Removed old internal modules rather than retaining forwarding facades; `sakai_mcp.asgi:create_app` remains the deliberate public entrypoint.
- Preserved inbound token verification and certificate-backed OBO as separate modules. Typed Sakai operation groups share one bounded transport; the generic grading tool-name dispatcher and model registry are removed. Proposal read and creation are explicitly separate operations.
- Extracted proposal/payload orchestration and resource evidence resolution from SDK handlers. SDK links/content remain in presentation; canonical computation and reports remain pure. Resource dependencies are constructor-injected.
- Composed app-owned HTTP cleanup with the existing SDK lifespan; injected clients remain caller-owned. Startup/shutdown failures are covered.
- Grouped native Java into security, courses, announcements, assessment, shared contracts and grading. Replaced the large grading coordinator with focused authorization, evidence, Gradebook projection, query, file, export, proposal, mutation and storage components.
- Retained native service calls, JSON map DTOs, request-local identity and lock closures. All 55 extracted native grading method bodies were compared using the Java compiler parser, normalizing only the added collaborator receivers; no unexpected method-body changes were found. Shared contract primitives were moved intact from assessment to `McpContractSupport`.
- Organized unit tests by responsibility and extracted reusable synthetic fixtures. Added independent schema/provenance snapshots, layer checks, lifecycle tests, multi-page manifest failure checks and proposal transport checks.
- Separated shell configuration, Azure account/resource helpers and SSH helpers. Explicit login reads the shared subscription configuration. Existing human command paths and deployment routes remain stable.
- CI invokes the same `scripts/check-mcp.sh` used locally. Added formatting/import ordering and typed function definitions to existing lint/types/tests. The existing native CI test selection discovers the moved/new test classes.
- Corrected the image version label to `0.2.0`; server version comes from installed package metadata. Restricted source distribution inputs and excluded editor/cache artifacts after a local runtime socket was initially discovered in the default source-distribution selection.

## Compatibility evidence

`services/mcp/tests/contracts/catalog.json` was captured before source moves. Tests compare complete SDK-discovered schemas, descriptions, annotations, defaults and public names against it. The setup/grading flag combinations preserve 5, 8, 19 and 22 tools, with five resource templates only when grading is enabled.

The synthetic `grading.json` baseline preserves evaluator output, exact CSV bytes, canonical output hash and the source fingerprint recorded by `inspect.getsource(evaluate_mcq)`. The evaluator's function source remains unchanged and its module is intentionally excluded from automatic formatting.

The native Spring wiring test resolves actual grading services through component scanning/qualified constructors and verifies all fifteen grading routes. Existing ordinary-login, delegated-session, permission, partial/unknown mutation, receipt, roster, export and grading tests continue to pass.

## Results

| Check | Result |
| --- | --- |
| Python tests, development Python 3.14 | 159 passed |
| Python tests, isolated locked Python 3.11 environment with the built non-editable wheel installed | 159 passed |
| Ruff lint/import order and format checks | Pass; evaluator formatting exclusion intentional |
| Mypy with typed function definitions | Pass, 37 source files |
| Native Java 17 reactor, MCP plus ordinary login | 72 tests passed, zero failures/errors/skips; build success |
| Native extraction body comparison | 55 methods match after accounting for collaborator receivers |
| Source distribution and wheel build | Pass |
| Non-editable built-wheel import check | All 36 submodules import without runtime credentials |
| Package contents | No local editor directory, runtime host-test tree or socket in wheel/sdist |
| Bash syntax and ShellCheck error checks | Pass for affected operations and shared helpers |
| Repository guidance and whitespace | Pass |
| Container build and source/dependency/image security scans | Not run locally: Docker daemon is unavailable; existing CI gates retained |
| Azure/runtime/client acceptance | Not run; no deployment or activation performed |

## Reproduction

From `services/mcp/`:

```sh
uv sync --locked
../../scripts/check-mcp.sh
uv build --out-dir /tmp/sakai-mcp-dist
```

For an isolated minimum-version test environment, use a task-specific `UV_PROJECT_ENVIRONMENT` with Python 3.11; no change to the contributor's existing virtual environment is required.

From the repository root, with Java 17:

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@17 mvn -f apps/sakai/pom.xml -pl webapi -am \
  -Dtest='Mcp*Test,LoginControllerTests' -Dsurefire.failIfNoSpecifiedTests=false test
```

The local native verification included a clean WebAPI target before the final compile to avoid relying on classes at their old package locations. The existing reactor prerequisites and upstream compile warnings are unchanged.

## Release boundary and remaining limits

No dependency versions, Bicep resources, feature flags, database schema, storage paths or cleanup timer configuration were changed. No Azure resources were started/stopped, no academic records were changed, and no deployment or push was performed. Historical release/client evidence has not been promoted to fresh acceptance.

Container scans must pass in an environment with Docker before release. A reviewed, committed and pushed source revision is also required for the existing exact-commit deployment route. Since native packages changed, use the native-first procedure and preserve both rollback identities. Existing native DTO shapes were deliberately retained; broader typed-DTO conversion is a separate behavior-sensitive improvement rather than part of this extraction.
