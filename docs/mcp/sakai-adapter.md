# Sakai WebAPI MCP adapter

**Source organization — 15 October 2026:** native components are grouped by responsibility beneath the same MCP namespace. See [the native source map](../../apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/README.md) and [local verification](../evidence/mcp/restructuring-local.md). Routes, delegated identity, storage contracts and feature properties remain compatible.

The [MCP-only grading migration](../SAKAI_GRADING_MCP_RESOURCES.md) replaces the local importer with SDK resources and server proposal/report tools. Native resource/proposal endpoints preserve delegated permissions and existing grading gates; see its release requirements before deployment.

The migration adds the following internal delegated Sakai endpoints. MCP hosts use tools/resources on `/mcp`; only the Python Sakai adapter calls these paths with the separate downstream token.

| Method | Native path | Purpose |
| --- | --- | --- |
| GET | `/api/mcp/v1/courses/{site}/grading-assignments` | Paginated published assignments the actor can grade |
| GET | `/api/mcp/v1/courses/{site}/assignments/{assignment}/grading-submissions/{submission}/files/{file}?revision=...` | Current attachment or native inline HTML, scoped and revision checked |
| GET | `/api/mcp/v1/courses/{site}/assignments/{assignment}/grading-files/{file}?revision=...` | Assignment attachment with its own content revision |
| POST | `/api/mcp/v1/courses/{site}/assignments/{assignment}/grading-proposals` | Immutable private proposal record; no academic mutation |
| GET | `/api/mcp/v1/courses/{site}/assignments/{assignment}/grading-proposals/{proposal}` | Principal-bound proposal read; reauthorizes source export and expiry |

These routes require `mcp.assignment.grading.enabled`, existing native permission checks and the private store. Original grading/export/write REST DTOs remain backward compatible. The old public Python `/grading-artifacts` route is removed; its native export byte endpoint remains an internal adapter implementation detail.
For the implemented opt-in TA grading adapter, see [assignment grading design](../SAKAI_ASSIGNMENT_GRADING.md) and [local evidence](../evidence/mcp/assignment-grading-local.md). Its routes reuse delegated identity and remain independently disabled. Default V1 routes and assignment-setup gates are preserved.

The Sakai-side V1 adapter lives in tracked `apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/`. Its servlet paths are relative to Sakai's existing `/api` WebAPI context. It is **disabled by default**; enabling it for the development release requires the Phase 7 predeployment gate, and the release is accepted only after the Phase 8 live checks in the [runbook](../MCP_IMPLEMENTATION_RUNBOOK.md).

The [Sakai integration guide](../SAKAI_INTEGRATION_GUIDE.md) preserves broader native interface findings, including canonical EID mapping, GradebookNG mutation candidates and the observed announcement lookback limitation. Consult it before extending this adapter; this document remains the V1 route/authentication reference.

For the next-phase assessment context and Assignment publication coordinator, see [assignment setup research and implementation plan](../SAKAI_ASSIGNMENT_SETUP.md). Its routes are proposals, not part of the V1 route table below.

## Runtime properties

Set these as Sakai properties through the existing VM configuration procedure. They are non-secret values, but environment-specific values must be verified from the issued downstream token and Entra metadata. Do not paste tokens, private keys, or client secrets into Sakai properties.

The tracked [`configure-mcp-sakai.sh`](../../deployment/configure-mcp-sakai.sh) script writes only this marked runtime block and leaves the rest of `local.properties` intact. It records a one-time pre-MCP backup. Apply it before a guarded exact-commit deployment so that the existing release restart activates the settings; do not edit the file by hand on the VM. The script's inputs are non-secret values, but keep project-specific identifiers out of evidence.

| Property | Required meaning |
| --- | --- |
| `mcp.integration.enabled` | `true` only for a validated rollout; default `false` |
| `mcp.integration.issuer` | Exact `iss` of the Sakai API access token |
| `mcp.integration.tenant` | Exact `tid` of the accepted tenant |
| `mcp.integration.audience` | Exact Sakai API resource `aud`, distinct from the MCP resource |
| `mcp.integration.scope` | `sakai.mcp.access` delegated scope |
| `mcp.integration.jwksUri` | Trusted HTTPS JWKS URI from the tenant metadata |

The browser-facing `RequestFilter` runs first. The adapter filter runs only on `/api/mcp/v1/*`, requires Tomcat to see the request as HTTPS, rejects missing or invalid downstream bearer tokens, and resolves the verified `extn.SakaiEid` singleton array through Sakai's trusted external evidence path. It rejects disabled/unmapped accounts and any mismatch between the token identifier and resolved Sakai EID. It creates and invalidates a separate request-local Sakai session, then restores the previous context. The code never accepts an identity header or relies on a browser cookie for this path. The MCP service owns the certificate-backed OBO exchange; Sakai has no OBO credential.

## V1 routes

| Method and path after `/api` | Behavior |
| --- | --- |
| `GET /mcp/v1/courses` | Up to 500 visitable course IDs and titles for the acting user |
| `GET /mcp/v1/courses/{siteId}/grades/me` | Released gradebook items and only the acting user's grade |
| `GET /mcp/v1/courses/{siteId}/announcements` | Visit-gated, viewable main-channel announcements; bounded to 50 results |
| `GET /mcp/v1/courses/{siteId}/assignments/{assignmentId}/submissions` | Up to 100 submitted records with ID, submitter IDs, and time; requires grade permission and filters group/section visibility |
| `POST /mcp/v1/courses/{siteId}/announcements` | The only V1 write; posted plain announcement in the main channel after Sakai `annc.new` authorization |

All course paths require `SiteService.getSiteVisit` before reading or writing a course object. The generic WebAPI announcement route is not reused because its live cross-site probe exposed unrelated announcements. The grades route never accepts a target student ID. The write route does not retry an ambiguous commit; callers must not replay it automatically.

## Local verification

Use Java 17 and the Sakai reactor, because WebAPI depends on sibling Sakai modules:

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@17 mvn -f apps/sakai/pom.xml -pl webapi -am \
  -Dtest='Mcp*Test,LoginControllerTests' -Dsurefire.failIfNoSpecifiedTests=false test
```

The local command and focused results are recorded in [`phase-7-sakai-adapter.md`](../evidence/mcp/phase-7-sakai-adapter.md). The development adapter was deployed through the existing guarded exact-commit release and passed the live delegated and ordinary-login checks in [`phase-8-release.md`](../evidence/mcp/phase-8-release.md). For subsequent changes, use the same [Sakai release procedure](../SAKAI_RELEASES.md) and repeat the focused tests and public acceptance checks. Code rollback does not revert the runtime MCP property block or any announcement created after deployment.

## Opt-in assignment setup endpoints

Local next-phase source adds the following paths inside the same request-local bearer boundary. They independently require `mcp.assignment.setup.enabled=true`; absent/false returns 404. The corresponding Python catalog requires `ASSIGNMENT_SETUP_ENABLED=true`. Neither flag is enabled by this source change.

| Method | Route | Behavior |
| --- | --- | --- |
| GET | `/api/mcp/v1/courses/{siteId}/assessment-context` | Bounded instructor metadata with paired optional RFC3339 `window_start`/`window_end`; no grades/submissions or backing-tool initialization. |
| POST | `/api/mcp/v1/courses/{siteId}/assignments` | Validate before safe native draft creation; coordinate selected new external item/deadline before posting. |
| POST | `/api/mcp/v1/courses/{siteId}/assignments/{assignmentId}/publish` | Revision-checked, author-owned promotion/recovery under a refreshed database row lock; no arbitrary editing. |

Writes check native add/revise and assessment-edit permission, ownership, category compatibility, finite dates/points and existing resources. A posted identical request is verified unchanged; partial results retain known IDs without delete/recreate or POST replay. Grade scores stay unreleased. Native auto-announcement is never invoked. The Calendar visibility interval and cross-service transaction limits remain explicit.

Use the expanded native-module test command and release checklist in [local evidence](../evidence/mcp/assignment-setup-local.md). These endpoints are not part of an accepted deployed V1 catalog.

For a separately authorized activation, pass the optional seventh `true` argument to the tracked `configure-mcp-sakai.sh` procedure and explicitly select `assignmentSetupEnabled=true` for the MCP app template. Omission of the script argument preserves an existing gate value; a new installation defaults false. No activation command was run during local implementation.
