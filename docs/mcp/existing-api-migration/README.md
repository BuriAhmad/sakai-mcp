Git organization (19 October): the migration source is now committed on
`codex/replace-custom-sakai-api`; `codex/sakai-custom-native-api` has its own
worktree at the original `208d69ac` baseline. See [worktree usage and verification](git-worktrees.md)
and [the separate organization record](git-organization.json). Original baseline,
implementation-start and private checkpoints remain unchanged. Statements below
about an uncommitted tree or fixed HEAD describe their dated checkpoints;
`--verify-progress` verifies the saved migration source, explicit organization
metadata paths and hash-chained dated continuation records after that commit.

Current local status (21 October, later attempt):21 facades wired to existing HTTP/external records, with T09 full regression gate OPEN. Full suite567 passed/17 failed; no failure repair. T20 complete-source preparation remains unproven. Native retirement stays22/23. See [remaining-tool evidence](remaining-tools-2026-10-21.md).


[Known tool limitations](tool-limitations.md) is the consolidated current reference for per-tool restrictions, caps, errors, evidence gaps and resolution gates.

# Sakai existing HTTP migration — canonical plan and checkpoint

**Start here: [complete implementation plan](implementation-plan.md).** This one Markdown file is the canonical implementation authority. It includes branch/base preservation, auth-first native work, capability-by-capability replacement/removal, all tool/resource research and flows, file/data ledgers, verification and runtime release gates. JSON inventories and the browser companion are supporting evidence; Downloads is a synchronized delivery copy. Local implementation resumed on 18 October 2026 on `codex/replace-custom-sakai-api`; see [current T01 cutover](t01-course-cutover-2026-10-19.md) and [progress](progress.json). The checkpoint sections below are historical.

The checkpoint sections below describe their original Phase 0 date/state.

**Later research amendment:** the user expanded scope to existing browser HTTP workflows for every tool/resource. See [browser HTTP research](browser-http-research.md) and [all 22/five ordered flows](browser-flows.json). Announcement creation, draft/publication and individual Gradebook-read candidates are now identified. These source findings supersede Phase 0’s API-only absence assumptions; delegated dynamic verification is pending. The Phase 0 checkpoint below remains historical evidence, not a claim that later scaffold/research additions did not occur.

Recorded 17 October 2026. **Local preservation and scope inventory are complete. No runtime migration has occurred.** Python still uses the legacy business routes. Existing tests demonstrate current compatibility, not compliance with the corrected architecture.

The complete plan is now [implementation-plan.md](implementation-plan.md); `/Users/burhanahmadkhan/Downloads/Sakai-Existing-APIs-Migration-Plan.md` is its synchronized delivery copy. Original Phase 0 hashes remain immutable in [baseline.json](baseline.json); current plan authority/hashes are recorded separately in `coverage.json` and `browser-flows.json`. Independent enumeration corrected two count statements: `McpAssignmentGradingController` has **14** method mappings; grading discovery adds **one**, for **15 combined**, not sixteen. There are **23 custom business routes overall**. No interface was omitted.

## Boundary and changes made

Sakai business operations must use existing upstream HTTP APIs. Parsing, normalization, pagination, computation and workflow coordination belong in Python. The sole permitted native extension establishes and cleans up delegated authentication/session context for selected existing handlers. No new endpoints, domain services, model/schema changes or changes to ordinary login are permitted to facilitate MCP.

Phase 0 adds only this evidence directory and the count correction in the separately requested plan. All preexisting repository files remain byte-for-byte unchanged, including uncommitted restructuring, guides, CLI/SSH changes, fixtures and editor configuration. No commit, push, deployment, feature activation, resource start/stop, academic mutation, schema operation or storage cleanup occurred.

## Evidence

| File | Contents | Limits |
|---|---|---|
| [baseline.json](baseline.json) | Exact HEAD/import/tree IDs; all 188 expanded dirty entries, classifications, hashes and modes; fixture hashes; private checkpoint and plan provenance | Not a reviewed commit, deployed revision or runtime/data backup. Editor files fingerprinted only. |
| [coverage.json](coverage.json) | 22 tools, five resource templates, four gate combinations, registrations/functions, native dependencies, research cards, owners, phases, gates, per-tool replacement matrix rows and D1–D8 | Eight defaults use existing HTTP with disclosed limits; nine routes retired locally. Fourteen tools and five resource families still need completion; live acceptance remains open. |
| [native-change-ledger.json](native-change-ledger.json) | 57 native changed/added/deleted paths versus import; grouped actions, replacements, dependencies, risks and tests; private-store/cleanup wiring | Deleted flat paths reflect restructuring, not retirement. Preserve native data and unrelated changes. |
| [route-references.json](route-references.json) | 109 repository files with reference locations/categories; ignored-consumer summary; separate installed-skill references | Reference inventory is not runtime reachability proof. No bodies, credentials or student content copied. |
| [check_scope.py](check_scope.py) | Read-only comparison of coverage with frozen catalogs, actual registrations/functions and native mappings | Checks inventory integrity, not final architecture/live acceptance. |

Native groups distinguish authentication integration, business code to retire, Assignment changes needing ordinary-UI/security review, Gradebook changes needing independent defect review, build/registration wiring, unrelated course layout/roster work and guidance. A file may contain both retirement hunks and separate defect fixes; a group does not authorize whole-file rollback.

A hidden dependency is explicit: `GradingWorkflow.prepare_grade_payload` hashes in Python but currently sends `mode=validate` through native save/release endpoints. Both are inventoried. The five MCP resource families also depend on native file/export/proposal routes; resource URIs do not eliminate those dependencies.

## Preservation and recovery

The owner-only archive is `/Users/burhanahmadkhan/Downloads/Sakai-Migration-Baseline-2026-10-17/working-tree-checkpoint.tar.gz`. Its private directory also holds checkpoint metadata, the original plan and ignored-consumer reference inventory. It contains current non-editor dirty source and HEAD originals for changed tracked files. Every included current file was read back and matched to its SHA-256.

All **188** preexisting dirty paths were classified. **Four** editor files were excluded from the archive and left untouched; their hashes are retained. Ignored credentials, uploads, database/runtime artifacts and build outputs were not archived. A separate read-only scan screened **116** ignored Python/shell candidates and found **seven** reference-bearing scripts. Their exact paths, hashes, line numbers and categories are private; their bodies and historical identifiers are not copied into repository evidence. None was run or changed.

Recovery is selective: inspect members and baseline hashes before restoring individual files. Never extract over the whole checkout, reset/clean it or overwrite newer user work. This archive does not replace Git history, a later reviewed migration base or runtime backups. Do not commit it or the private consumer report.

## Fresh local verification

From the repository root:

```sh
python3 docs/mcp/existing-api-migration/check_scope.py
python3 docs/mcp/existing-api-migration/check_scope.py --verify-working-tree
```

The second command is **Phase 0 only**: it verifies original path presence/bytes, unchanged HEAD and the private archive hash. Future intentional implementation will naturally invalidate this preservation check. Keep the original baseline immutable and record new reviewed revisions/diffs rather than rewriting hashes to hide changes.

The normal scope check verifies 22 tools, five resources, 23 routes (15 grading), all four catalogs, D1–D8, functions and complete native-route dependency coverage. Missing coverage, unknown mappings/dependencies and changed frozen contracts fail. New Spring mapping syntax requires review rather than silent omission. It does not scan every possible future replacement endpoint or prove final runtime behavior; implement the broader architecture gates in plan section 12 before cutover.

Freshly passed:

```sh
cd services/mcp
uv sync --locked
../../scripts/check-mcp.sh
```

Lint passed; 73 Python files passed formatting; mypy found no issues in 37 source files; **159 tests passed**, including full schemas/discovery for all flag combinations and evaluator/CSV/provenance comparisons. `uv sync` updated the ignored local environment to the existing lockfile; source and lockfile stayed unchanged. No Java behavior changed, so historical native results were not rerun or presented as fresh evidence.

No live check was needed. Installed native revision, properties, schema, private store, sessions and delegated existing-handler behavior remain unverified in this phase. Earlier Azure observations and reports retain their original dates. Do not start compute, refresh firewall rules or execute mutation helpers to close these gaps without the relevant authorization.

## Gate and next implementation phase

Phase 0's local preservation/coverage gate passes. HEAD `208d69ac624910a29a7529934ddcc18bbac853e8` plus the fingerprinted uncommitted tree is a recoverable proposed base. No unrelated work was committed to manufacture a clean base. Selection of reviewed commits remains part of normal implementation review.

Next is **Phase 1: isolated existing-API contracts, operation descriptors and parsers**, leaving current routing unchanged until authenticated-handler/role evidence supports cutover. Use plan sections 5–8 and `coverage.json` research cards; preserve public compatibility fixtures.

1. Use typed unknown/omission/completeness semantics, bounded parsing and semantic retry classification. Mutating GETs never receive read retries. A grader average is never an own grade; an omitted field is not automatically false.
2. Preserve Direct Assignment list hydration and scoped-TA over-fetching as blockers. Safely investigate A14 and lean SOAP coverage before accepting loss. No new Java endpoint may fill a gap.
3. D1 announcement create, D2 controlled setup/publication, D3 concurrency/save semantics and D4 public coverage remain explicit decisions. No implicit catalog reduction, fabricated parity or administrator fallback.
4. Design the auth-only extension per servlet context and existing handler, preserving Entra/OBO identity and ordinary login/API consumers. Do not broadly remap the current namespace filter.
5. Retire native business code only after Python/client compatibility, retained legacy records, ordinary-UI/security regressions and authorized release ordering pass. Never automatically drop the version column or delete exports, proposals, links, receipts or cleanup dependencies.

Runtime starts, releases, feature activation, provisioning/cleanup and academic writes remain separate future authorization boundaries. This checkpoint grants none of them.

## Current implementation verification (18 October 2026)

`implementation-start.json` records the reviewed 201-path start and fresh private
checkpoint. `progress.json` lists intentional changes without replacing the
original Phase 0 hashes. Use:

```sh
python3 docs/mcp/existing-api-migration/check_scope.py --verify-progress
```

Fresh Python verification passes **330 tests**, lint, formatting and mypy. Fresh
Java 17 verification passes **89 tests**, including real RequestFilter/Sites and
Tomcat Portal dispatch with a synthetic target. Course discovery has an explicit
existing-HTTP mode; its default remains legacy. Native business form/role
acceptance, per-capability cutover/retirement, D3 and D6 remain open. See the
[local evidence and next gates](local-integration-2026-10-18.md). There was no
deployment, runtime change, academic write or data deletion.

Latest increment: [existing reads and placement discovery](read-discovery-2026-10-18.md).
Current fresh checks pass **360 Python tests** and **100 Java tests**. T03 now has an
explicit existing announcement-read mode; B0 placement discovery uses the existing
native pages action. The auth response boundary also withholds native session
credentials from diagnostic bodies/headers. Defaults and all legacy consumers
remain until per-capability acceptance permits cutover and focused retirement.

T01 additionally supports published public courses using fresh native ACCESS
selection plus effective permissions, preserves the original sorted 500-course
cap and handles native page-size clamping. Masked ambiguity, native role/cache
parity and large-inventory performance remain explicit acceptance gates.


## T01 default cutover (19 October 2026)

`list_my_courses` now always uses existing HTTP interfaces. Its old course-list
method/route and temporary selector/helper are removed locally. The shared
announcement controller method remains. Coverage retains all 23 historical route
entries and verifies the 22 active mappings against source. See
[T01 evidence](t01-course-cutover-2026-10-19.md) for fresh checks, preservation,
release incompatibility with older clients and remaining live gates. Earlier
checkpoint results above are historical, not current verification.

## Continuation after Git organization — 19 October 2026

[External capture and selected-grade evidence](external-capture-cutover-2026-10-19.md)
records five more default replacements (13 total), seven more retired routes
(16 retired, seven active), precise partial-functionality and MCQ blockers.
`continuation-2026-10-19.json` pins the new reviewed changes and private checkpoint
against `0f9f44a7`. Original baseline/start/Git-organization manifests remain
immutable. `check_scope.py --verify-progress` checks both preservation eras; the
original `--verify-working-tree` remains historical. Neither Git worktree nor any
runtime was reorganized or deployed. Follow current coverage/progress/limitations
for ongoing implementation; earlier test counts in this README are dated history.

## Readback continuation — 20 October 2026

[Selected readback evidence](readback-2026-10-20.md) records Gradebook point display
readback and rendered native grading-list pagination through T16's existing default.
No new tool completion or native retirement is counted. The native missing-row
template has no stable UID, so B7 completeness and T20's complete-evidence gate stay
open. Fresh checks: 481 Python tests, lint/format/types, wheel/sdist and scope pass;
no native source change or new Java/live acceptance. The new October 20 preservation
record pins the October 19 record unchanged and validates prior/final bytes across
the continuation chain. Original manifests/checkpoints remain immutable.

## Practical setup continuation — 20 October 2026

[Setup evidence](setup-cutover-2026-10-20.md) records T06/T07/T08 actual-default
cutover, useful partial functionality, three further route retirements and the
remaining shared grading revision dependency. Original public schemas/catalogs
remain frozen. Named continuation records preserve multiple reviewed increments
on the same date without rewriting prior records. All live/deployment gates remain
separate; earlier counts and evidence retain their original dates.


## Grading-context/payload dependency review — 20 October 2026

The T09/T18 source review confirmed that the frozen grading context cannot yet
represent several unknown Assignment fields, and the existing `http1-` revision
projection is incompatible with the active native save/release revision check.
T18 also relies on current-state native validation; replacing it with schema-only
checks would overstate what was verified. No routing or completion count changed.
See [the source-backed review](grading-context-payload-review-2026-10-20.md) and
current [limitations](tool-limitations.md) for the next coordinated gate.

### Grading write continuation — 20 October 2026

[Fresh grading write evidence](grading-write-2026-10-20.md) records actual T14/T15/T18
HTTP defaults for the supported subset, two route/coordinator retirements and
preservation. Current totals: 20/22 defaults replaced locally, 22/23 historical
routes retired; T09 and T20 remain. No resource family is fully migrated. Earlier
counts are dated history. Nothing is live or deployed by this local cutover.

[Context/MCQ and helper review](evidence-review-2026-10-20.md) records further
source evidence and retirement of four unused native mutation methods. No new
tool/default completion: totals remain 20/22 defaults and 22/23 retired routes.

[Attachment handler proof](attachment-proof-2026-10-20.md) adds reproducible native
stream/denial/filter/redirect/sendfile tests and guarded rejection through current
resource facades. Content/roster routes remain unaccepted; no default count change.

## Development line separation — 20 October 2026

The [maintained worktree guide](../../DEVELOPMENT_WORKTREES.md) separates original baseline, auth development and tool migration development. The original `sakai-mcp` checkout and its continuation checks remain the mixed recovery source. This tool-development checkout uses its role/source-anchor verifier and the separate auth dependency. No failed proof is repaired by organization.
