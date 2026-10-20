# Transitional native Sakai MCP integration

The [canonical migration plan](../../../../../../../../../../docs/mcp/existing-api-migration/implementation-plan.md) governs replacement and focused retirement. These native business routes are transitional dependencies. Only delegated authentication/session integration may remain in Sakai.

Twenty defaults now use existing HTTP/external records, with explicit partial
functionality and live/legacy gates. Twenty-two routes are retired locally; only grading-context
remains. See [current evidence](../../../../../../../../../../docs/mcp/existing-api-migration/grading-write-2026-10-20.md)
and [limits](../../../../../../../../../../docs/mcp/existing-api-migration/tool-limitations.md).
Current inline and captured inline evidence are supported; current attachment
retrieval remains unsupported. This native revision is incompatible with older
Python clients needing retired routes: release additive auth, accepted matching
Python, then authorized native retirement.

The remaining `/api/mcp/v1/*` routes run inside Sakai WebAPI using the verified downstream bearer identity and ordinary native permissions. Packages follow responsibilities within the existing Maven module:

| Package | Responsibility |
| --- | --- |
| `security` | JWT verification and isolated request-local Sakai sessions |
| `assessment` | Retained configuration revision helper for current grading context callers |
| `contracts` | Shared contract primitives such as canonical references, safe errors and hashing |
| `grading` | Grading context, shared evidence and preserved legacy private storage |

The grading controller delegates directly to focused services:

- `McpGradingAuthorization`: acting user, assignment/site equality, group scope and capability restrictions.
- `McpGradingEvidence`: retained context identities, attachments and observed revision/flag mapping.
- `McpGradebookProjection`: owned external links and target eligibility.
- `McpGradingQueryService`: context and retained roster helpers.
- `McpGradingStore`: the existing canonical private store, locks and atomic records.
- `McpGradingJson`: native grading decimal/JSON/request primitives.

Services use constructor injection and retain the original native service calls, permission order, submission lock closures and persisted fields. No new transaction annotations or database migration are introduced by the structural extraction. Existing JSON map DTOs remain compatible; typed-DTO conversion can be reviewed separately.

Tests mirror these packages under `webapi/src/test/java/`. `McpGradingServicesTest` exercises the actual extracted components; `McpGradingWiringTest` verifies component scanning, qualifiers and the sole remaining native grading-context route and retired-class absence. Existing bearer/session and ordinary login tests remain in the focused test selection.

From the repository root, with Java 17 configured:

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@17 mvn -f apps/sakai/pom.xml -pl webapi -am \
  -Dtest='Mcp*Test,LoginControllerTests' -Dsurefire.failIfNoSpecifiedTests=false test
```

The web context scans `org.sakaiproject.webapi`, so these subpackages remain discoverable. The `mcpBearerFilter` bean name and `/mcp/v1/*` filter mapping are unchanged. Source package changes do not activate native properties or authorize deployment.

The [external-capture cutover](../../../../../../../../../../docs/mcp/existing-api-migration/external-capture-cutover-2026-10-19.md)
retired file/export/proposal controllers/services and the selected-grade query
method locally. Only the grading-context custom business mapping remains. Python owns new partial inline captures and
frozen proposal/resource reads; legacy private records and cleanup ownership remain
preserved pending D6. Removed native routes require compatible Python cutover
before any native deployment; no source change establishes live acceptance.

The setup cutover retires both assessment/setup controllers and
`McpAssignmentSetupService`. `McpAssessmentService` retains only its unchanged
configuration revision calculation for `McpGradingQueryService`; its unused
context/calendar/Gradebook coordination is removed.
Native ordinary handlers/models, auth integration and all records/schema remain
preserved. Source retirement does not authorize deployment against older Python.

The T17 cutover removed the operation-read mapping. T14/T15 now use existing
Direct grading HTTP through Python for the disclosed subset; their mappings and
`McpGradeMutationService` are retired. Original native records, stores, domain
helpers and cleanup remain preserved; legacy import/drain is unresolved. The four unused
mutation-only helper methods and their unused constructor dependencies are now retired
after caller review; context evidence/link/capability methods remain. No new native
business endpoint or ordinary handler change is introduced. The auth-only module
limits delegated POST reach to the exact selected existing URL-encoded action.
Legacy compatibility and authorized release ordering remain open.

The evidence-review continuation retires `McpGradebookProjection.writeTarget/target`
and `McpGradingEvidence.revision/current` only. Evidence no longer injects metadata
or authorization; projection no longer injects Assignment/Site/GradingAuthz/evidence.
Query still owns the native semantic revision and ordinary context permission path.
No native store/schema/domain or ordinary Assignment/API cleanup is included.

## Separate auth dependency

This tool-development line excludes the new native auth framework and servlet wiring. The Python client/flow protocol is retained unchanged and pinned in `docs/mcp/development-lines/role.json`; native auth compatibility/acceptance must be assembled separately. Do not repair the recorded attachment proof failures or change server auth here. See `docs/DEVELOPMENT_WORKTREES.md` for ownership.
