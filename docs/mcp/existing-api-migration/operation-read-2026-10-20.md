# Revision inputs and external operation receipt cutover — 20 October 2026

Actual local default replacement: **T17 `get_assignment_grading_operation`**.
Seventeen of 22 defaults are replaced locally; five remain. Twenty of 23 historical
business routes are retired locally; three remain for context/save/release. This
is partial functionality, not full migration, live acceptance or deployment.

## Revision source review

The retained native hash is `McpAssessmentService.revision(Assignment)`. These are
all 22 keys it hashes, with availability in the researched existing interfaces.
“Direct” means `AssignmentEntityProvider.SimpleAssignment`; JSON and XML serialize
the same DTO and do not provide different underlying fields.

| Hash input | Existing evidence and remaining limit |
| --- | --- |
| `id` | Direct `id`; verify selected ID/site relationship. |
| `title` | Direct `title`. |
| `instructions` | Direct `instructions`; retain exact observed text, not rendered/sanitized equivalence. |
| `draft` | Direct `draft`. |
| `deleted` | Not emitted by the Direct DTO; reachability/status alone is not the raw Boolean input. |
| `visible` | Not emitted; editable date control has native minute/timezone representation, not guaranteed exact stored Instant. |
| `open` | Direct `openTimeString`; parse exact Instant. |
| `due` | Direct `dueTimeString`; parse exact Instant. |
| `close` | Direct `closeTimeString`; parse exact Instant. |
| `points` | Direct maxima are display units; not the raw integer without proven scale. |
| `scale` | Raw per-Assignment scale is not emitted by this DTO. Never use server defaults to reconstruct it. |
| `grade` | Direct `gradeScale` enum name. |
| `submission` | Direct `submissionType` enum name. |
| `audience` | Direct `access` enum name. |
| `group` | Group access/selected groups do not establish `getIsGroup()`; native list gives a supported individual-mode observation, not a complete raw configuration projection. |
| `groups` | Direct `groups` originates from the stored group collection; bound/validate all references and ordering. |
| `release` | Raw Assignment `getReleaseGrades()` is not emitted; a submission's released/returned cell is a different field. |
| `peer_assessment` | Direct `allowPeerAssessment`. |
| `content_review` | Edit controls reflect available review configuration; not a verified raw Boolean for all permitted grader views. |
| `individual` | Direct omits `getIndividuallyGraded()`; edit/grader mode must not be guessed. |
| `attachments` | Direct decorates resource references and silently drops invalid attachments; it cannot prove the full exact stored reference list. |
| `properties` | Direct PropertiesProvider returns a curated descriptive/security map, not `a.getProperties()`. Edit forms expose selected controls, not the complete arbitrary property map. |

Source locators:

- `apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/assessment/McpAssessmentService.java`: exact hash inputs.
- `apps/sakai/assignment/tool/src/java/org/sakaiproject/assignment/entityproviders/AssignmentEntityProvider.java`: `getEntity`, `getAssignment`, `getProperties`, `SimpleAssignment`; JSON/XML share this projection; attachment mapping catches and drops failures.
- `apps/sakai/webservices/cxf/src/java/org/sakaiproject/webservices/Assignments.java`: `getAssignmentsForContext` emits ID/title/grade type and selected dates, not raw configuration/properties.
- `apps/sakai/assignment/impl/src/java/org/sakaiproject/assignment/impl/AssignmentServiceImpl.java`: `archive` uses repository XML and includes additional native state.
- `apps/sakai/webservices/cxf/src/java/org/sakaiproject/webservices/SakaiScript.java`: `archiveSite` requires superuser and calls `archiveAndZip`; this is not an accepted delegated read or a metadata workaround.

No researched delegated read reconstructs every legacy hash input. T09/T18 remain
unmigrated while current T14/T15 consume that native hash. This finding does not
forbid independently useful existing-read subsets. It also corrects the earlier
review's overbroad dry-run inference: **Python advisory validation may use read
preflight; it does not require a native UI `validate` action.** Sufficient state,
honest validation results and revision compatibility remain the actual gates.

## Actual default and callers

`mcp/tools.py:get_assignment_grading_operation` still calls the original
`GradingOperations` facade and presents the frozen native/public result. The
facade now uses `workflows/grading_operations.py:GradingOperationsJournal.read`.
There is no native operation-read fallback or selector. The current actor/site and
positive individual grading view are established through `SubmissionReads`; each
record's exact selected submission/user pair must still be currently authorized.
Group-only, anonymous, missing/withdrawn or omitted targets may fail explicitly.

The reader validates the owner-bound `PrivateRecords` envelope, expiry if present,
`grading-receipt-transition-v1` provenance, exact typed approved request, operation
ID/kind/mode, semantic payload hash, receipt digest and exact unique row set.
It returns the original historical timestamp/stages/outcome. Current matching
values never establish causation or change an unknown outcome. Historical
Gradebook scores are withheld with a warning because this read does not establish
current item/student authority. Original warnings are preserved; if adding required
limitations exceeds the frozen 30-warning limit, the read fails unsupported.
Reads change neither storage nor expiry and issue no academic POST.

## Preserving the active writers

T14/T15 still use native business save/release routes and are **not** counted as
migrated. To avoid breaking receipt lookup for these active writers, Python now
requires configured durable external storage before commit HTTP. It validates the
canonical payload/unique target set, establishes current source scope, durably
creates a unique Prepared intent, and persists Sending with conditional replacement
before the sole native POST. A matching confirmed native reply is saved externally.
The native mutation's existing permissions, validation, locking, store and academic
behavior remain unchanged. Validation mode still calls native preflight without
academic commit and creates no operation journal.

A second worker or repeated ID receives the stored outcome and never sends again,
even if the saved intent is only Prepared. Different payloads conflict. A lost reply,
malformed/mismatched result or failed receipt persistence leaves the external
outcome unknown; subsequent reads never replay or resume it. A process crash after
Prepared/Sending is intentionally not an automatic recovery mechanism. Native
preflight failures may also leave conservative unknown external state.

## Focused native retirement and compatibility

Removed only `McpAssignmentGradingController.operation` and
`McpGradeMutationService.operation`, plus the optional synthetic emitter for that
retired method. The old native read only reauthorized and returned its receipt;
it did not reconcile unknown rows. Source/wiring tests verify exactly three routes
remain. Shared write helpers, native operation records/idempotency lookups,
`McpGradingStore`, cleanup, authentication, Assignment/Gradebook services and schema
are retained. No entire native class was newly deleted; the 11 earlier retired
business classes remain absent from the rebuilt WAR.

Existing native-only receipts have no automatic importer or new read fallback.
They are preserved and require a reviewed owner-bound import/drain. Do not issue a
new commit to discover an old receipt. The transitional external record schema and
nonexpiring operation policy are local implementation; durable backend ownership,
retention/backups, legacy import and actual-role acceptance remain D6/D8 gates.

Release order remains additive compatible native auth → accepted matching Python
cutover → separately authorized native retirement. The native tip is incompatible
with older Python operation readers. No release/configuration inventory, live
acceptance, feature activation, runtime change, academic operation or cleanup took
place.

## Fresh verification

- Locked dependency sync; full `scripts/check-mcp.sh`: **551 Python tests**, Ruff
  lint/format across **126 files**, mypy across **71 source files**; frozen public
  schemas/catalogs/descriptions/evaluator/report checks unchanged.
- New facade tests cover confirmed partial receipts, exact target/hash/owner/
  provenance/expiry failures, current permission/identity denial, warning budget,
  no-store/no-send, same-ID conflicts, two-worker single-send, Prepared/no-resume,
  lost native reply, failed final receipt persistence, release wiring and immutable
  read behavior. The SDK/JWT/OBO pipeline exercises public save → external
  operation lookup plus student denial with synthetic source-derived HTTP.
- Java 17 focused reactor: **47 tests in eight suites**, zero failures/errors/
  skips, BUILD SUCCESS. Includes retained grading semantics, three-route Spring
  wiring, delegated auth, existing Sites/Portal and ordinary Login tests.
- Fresh Python wheel/sdist and Java17 package builds passed. Packaged Python source
  bytes match the new workflow/facade. Rebuilt WAR class bytes match current output,
  contain no operation-read mapping/method, and exclude all 11 previously retired
  business classes. No blanket clean or generated-class deletion was needed.
- Repository guidance/whitespace and final scope/preservation checks are recorded
  in progress and the named continuation. Original manifests/continuations/private
  archives and both editor directories are preserved; index remains empty.

Next: compatible T09/T18/T14/T15 existing-HTTP preflight/save/return design with
explicit field preservation and D3 uncertainty; T17 legacy/retention acceptance;
complete roster/content evidence before MCQ. No local test result establishes a
live or deployed grading workflow.
