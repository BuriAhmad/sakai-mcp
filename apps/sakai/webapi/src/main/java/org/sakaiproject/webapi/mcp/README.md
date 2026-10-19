# Transitional native Sakai MCP integration

The [canonical migration plan](../../../../../../../../../../docs/mcp/existing-api-migration/implementation-plan.md) governs replacement and focused retirement. These native business routes are transitional dependencies. Only delegated authentication/session integration may remain in Sakai.

Eight tools now use existing HTTP handlers from Python, including own grades,
submitted metadata/evidence and announcement creation. Their nine custom routes
are retired locally. See [five-tool evidence](../../../../../../../../../../docs/mcp/existing-api-migration/five-tool-cutover-2026-10-19.md)
for the exact caller map and role/completeness/precision limits. Submission inline
text is replaced; attachment retrieval remains explicitly unsupported. Fourteen
business routes remain. This native revision is incompatible with older Python
clients that need retired routes: release additive auth, the matching Python
cutover, then native retirement. No deployment is authorized here.

The remaining `/api/mcp/v1/*` routes run inside Sakai WebAPI using the verified downstream bearer identity and ordinary native permissions. Packages follow responsibilities within the existing Maven module:

| Package | Responsibility |
| --- | --- |
| `security` | JWT verification and isolated request-local Sakai sessions |
| `assessment` | Assessment context and Assignment/Gradebook/Calendar setup coordination |
| `contracts` | Shared contract primitives such as canonical references, safe errors and hashing |
| `grading` | Scoped grading reads, evidence, exports, proposals, save/return and private storage |

The grading controller delegates directly to focused services:

- `McpGradingAuthorization`: acting user, assignment/site equality, group scope and capability restrictions.
- `McpGradingEvidence`: hydrated identities, attachments, revisions and submission preconditions.
- `McpGradebookProjection`: owned external links and target eligibility.
- `McpGradingQueryService`: context, retained roster and selected grades.
- `McpGradingFileService`: current files with revision/integrity checks.
- `McpGradingExportService`: immutable export capture, inventory, expiry and artifact reads.
- `McpGradingProposalService`: immutable owner-bound proposals and source-export reauthorization.
- `McpGradeMutationService`: approved validate/save/return, row locks, durable receipts and reconciliation.
- `McpGradingStore`: the existing canonical private store, locks and atomic records.
- `McpGradingJson`: native grading decimal/JSON/request primitives.

Services use constructor injection and retain the original native service calls, permission order, submission lock closures and persisted fields. No new transaction annotations or database migration are introduced by the structural extraction. Existing JSON map DTOs remain compatible; typed-DTO conversion can be reviewed separately.

Tests mirror these packages under `webapi/src/test/java/`. `McpGradingServicesTest` exercises the actual extracted components; `McpGradingWiringTest` verifies component scanning, qualifiers and the eleven remaining native grading routes. Existing bearer/session and ordinary login tests remain in the focused test selection.

From the repository root, with Java 17 configured:

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@17 mvn -f apps/sakai/pom.xml -pl webapi -am \
  -Dtest='Mcp*Test,LoginControllerTests' -Dsurefire.failIfNoSpecifiedTests=false test
```

The web context scans `org.sakaiproject.webapi`, so these subpackages remain discoverable. The `mcpBearerFilter` bean name and `/mcp/v1/*` filter mapping are unchanged. Source package changes do not activate native properties or authorize deployment.
