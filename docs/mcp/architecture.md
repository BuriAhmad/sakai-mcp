# Sakai MCP architecture

## Current required direction — 17 October 2026

The user clarified that the MCP service must use **existing Sakai APIs** for its operations. The permitted Sakai extension is limited to delegated authentication/session establishment. Response normalization, parsing, pagination, computations and workflow coordination belong outside Sakai in the MCP service. New Sakai domain endpoints, business-service changes and schema changes are outside that exception.

The sections below describe the implementation currently present in source, including custom `/api/mcp/v1/*` endpoints; they are not approval to continue or expand that architecture. Earlier runbook decisions to create native controllers are superseded by the user's integration boundary in [AGENTS.md](../../AGENTS.md#mcp-integration-boundary). Existing release evidence remains a historical record, not proof that the earlier architectural interpretation matched the user's requirement.

An authentication bridge can validate the delegated token and bind a Sakai user context before forwarding to an existing handler without creating domain endpoints. The existing filter's mapping only covers `/mcp/v1/*`; using existing API routes therefore requires a deliberate, scoped authentication-integration design and verification of the selected handlers and servlet contexts. Native session login and Sakai's existing OAuth implementation are other integration mechanisms to investigate, not verified replacements for the current Entra flow across all endpoints.

No migration is implemented by this documentation correction. A migration must inventory existing APIs for every tool, identity/session support, authorization and data minimization, write/retry semantics, and unavailable atomicity/reconciliation guarantees. Unsupported behavior must be reported rather than supplied through new native business code. Removal of existing code/schema/storage and deployment changes require a separate compatibility and release plan.

## Implementation currently present in source

The project has two application boundaries: the Python MCP service under `services/mcp/`, and the permission-aware native integration inside Sakai WebAPI under `apps/sakai/webapi/`. Azure infrastructure and release operations remain under `deployment/` and `scripts/`.

## Python responsibilities

All public tool definitions live in `services/mcp/src/sakai_mcp/mcp/tools.py`. That file owns signatures, descriptions, annotations and independent feature gates. `mcp/server.py` constructs the SDK server; `mcp/resources.py` owns resource discovery and SDK reads. Presentation is separate from evidence resolution and workflow decisions.

A simple course read follows:

```text
MCP tool -> Sakai course operation -> shared HTTP transport -> native Sakai
```

Proposal preparation follows:

```text
MCP tool -> grading workflow -> scoped Sakai reads + deterministic evaluator
         -> durable native proposal -> MCP response/resource presentation
```

The `contracts/` package keeps native REST DTOs separate from MCP resource-enriched DTOs and frozen proposal configuration. `workflows/` coordinates evidence, pagination, integrity and reconciliation without importing MCP presentation/server modules. `grading/` performs pure evaluation, canonical serialization and report generation.

Authentication and certificate-backed on-behalf-of exchange remain separate components under `security/`. Configuration and request audit retain dedicated modules. `sakai/client.py` owns one transport and exposes typed operation groups; there is no generic tool-name dispatcher or caller-selected destination. `bootstrap.py` constructs dependencies and composes cleanup with the SDK lifespan. `asgi:create_app` remains the deployment entrypoint.

See [the service source map](../../services/mcp/README.md) for file ownership, change entrypoints and developer commands. Skills consume the public API; they do not define runtime module boundaries.

## Native responsibilities

The native integration retains the existing WebAPI Maven module and component-scan root. Its MCP namespace is grouped into `security`, `courses`, `announcements`, `assessment`, `contracts` and `grading`. The grading controller injects focused query, file, export, proposal and mutation services, sharing explicit authorization, evidence mapping and the private store. See [the native source map](../../apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/README.md).

The refactor preserves native service calls, request-local sessions, submission row-lock closures, JSON DTO fields, durable record layout and expiry. Existing assignment evidence-loading and submission-version support remain in their original Sakai Assignment modules. There is no schema migration or new transaction annotation in the restructuring.

## Identity and permissions

Clients connect to authenticated stateless Streamable HTTP at `/mcp`. The service validates the MCP-audience token and delegated scope, exchanges it through certificate-backed OBO for a distinct Sakai-audience token, and independently validates the downstream token. Sakai resolves the verified `extn.SakaiEid` singleton to an existing user and establishes an isolated request-local session. The caller cannot select the acting user.

Native services remain authoritative for site visit, object/site equality, submission access, group scope and grade permissions on every call. Own-grade reads always return only the acting user's released grades. Course announcements use the visit-gated MCP adapter rather than the previously observed permissive generic WebAPI route. There is no generic URL proxy or administrator fallback.

The canonical OAuth resource is the verified public MCP origin plus `/mcp`. Its v2 token audience is the MCP application's client ID; Sakai remains a distinct issuer/audience resource. Health checks are local and do not call Entra or Sakai. Audit output excludes tokens, raw LMS identifiers, grades and student content.

## Catalogs and write boundaries

Source defaults expose five V1 tools; announcement creation is the sole V1 write. Assignment setup independently adds three tools. Grading independently adds fourteen tools and five resource templates. Both optional flags default false. The four combinations expose 5, 8, 19 or 22 tools. Feature activation remains a separate runtime action.

Grading exports/proposals are bounded private records, and academic save/return remain distinct approval steps. Unknown or partial write outcomes require reconciliation. JSON GET retry limits, single-attempt POSTs, read-only grade-query error handling, binary stream bounds and checksum checks are preserved. Persisted canonical hashes, report bytes and evaluator source provenance have pre-refactor compatibility tests.

## Validation and release

`./scripts/check-mcp.sh` runs lint/import ordering, formatting, types, architecture boundaries, contract snapshots and Python tests. Native tests continue through the Sakai reactor; the grading wiring test verifies Spring component discovery, qualifiers and all fifteen native grading routes. Package builds explicitly select source/test metadata and exclude local editor/runtime artifacts.

Local restructuring evidence is in [the verification record](../evidence/mcp/restructuring-local.md). Local results do not establish live acceptance or modify the historical release reports. Follow [the implementation runbook](../MCP_IMPLEMENTATION_RUNBOOK.md), [MCP releases](../MCP_RELEASES.md), [Sakai releases](../SAKAI_RELEASES.md) and [native-first grading release order](../GRADING_MCP_RESOURCE_RELEASE.md). No deployment, feature activation, capacity change or runtime start occurs as a result of source edits.

Workflow behavior is specified in [assignment setup](../SAKAI_ASSIGNMENT_SETUP.md), [assignment grading](../SAKAI_ASSIGNMENT_GRADING.md) and [grading resources](../SAKAI_GRADING_MCP_RESOURCES.md). The [integration guide](../SAKAI_INTEGRATION_GUIDE.md) distinguishes verified native interfaces from provisioning-only workarounds. Historical acceptance and remaining client limitations are recorded in the dated reports linked from [the implementation runbook](../MCP_IMPLEMENTATION_RUNBOOK.md).
