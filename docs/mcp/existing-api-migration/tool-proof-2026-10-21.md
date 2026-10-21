# Tool migration proof continuation — 21 October 2026

Local proof/research only. No production Python or Java implementation, frozen
contract/catalog/description/evaluator/report fixture, authentication behavior or
protocol was changed. No default switched and no native source retired.

## Source and preservation

Initial branch `codex/tool-migration-development`, HEAD
`833e7c4dc3844e0ddc545d47e92989e87fdc7140`, empty index and clean working tree.
`git worktree list --porcelain` matched the requested four-checkout arrangement.
Only this tool worktree was edited. Root/scoped guidance, the complete canonical
plan and its current inventories, separation/classification/verification and
Git/preservation records, integration guide and attachment audit/proof sources
were reviewed. Historical auth proof source is excluded here by extraction;
its recorded hashes/outcomes remain historical, rather than a current auth result.

Before editing, scope and development-line source checks passed. A private 206-file
source checkpoint was created and every archived member read back against its
hash. It is ignored at `deployment/artifacts/tool-proof-2026-10-21/` in this
worktree, owner-only. All ten prior continuation records and their private artifact
hashes were verified without rewriting them. The new preservation record is
`docs/mcp/development-lines/tool-proof-2026-10-21.json`; it pins the prior separation
record and original extraction/source anchors. The original immutable archives,
baselines, manifests, editor exclusions and continuation chain are preserved.

## Actual paths and fresh outcomes

| Proof/check | Expected | Actual and reached components | What it does not establish |
| --- | --- | --- | --- |
| Initial `uv sync --locked` then `../../scripts/check-mcp.sh` from services/mcp | Existing post-extraction regressions pass | PASS: 561 tests; lint/format/types pass | Historical 568/48 results are not fresh evidence here |
| New public MCQ gate | CONFLICT on a real current partial capture, no downstream grading work | PASS: SDK `call_tool` → registered T20 → GradingWorkflow → external proposal lookup/manifest and current synthetic HTTP reauthorization → complete-input rejection. Context/evaluator/create-proposal sentinels untouched; store objects unchanged; only GETs and no custom route | Complete-input evaluation, native delegated permissions, Blob durability or successful proposal preparation |
| New public T09 successful fixture | Retained native dependency and unavailable write capability hints | PASS: SDK → registered T09 → invoke_grading → GradingOperations._send → SakaiTransport → one mocked GET `/api/mcp/v1/courses/course-a/assignments/assignment-a/grading-context`; prepare/save/release false | An existing-HTTP replacement or actual servlet/auth reach |
| New T09 denial fixture | FORBIDDEN, no fallback | PASS: synthetic HTTP403 translated to ToolError; exactly one GET | Actual native ACL decision; this is a simulated HTTP response |
| New T09 missing required state (two cases) | Required scale_factor/native_release_grades are not guessed | PASS: synthetic200 missing each field yields INTERNAL_ERROR from strict model validation; exactly one GET | Completeness of real native serialization or field availability in every existing API |
| Unchanged positive attachment readiness | Three readiness probes execute and pass | ERROR: collection fails `ModuleNotFoundError: No module named 'tests'`, exit2; zero probes execute | Any application capability, content response or registration assertion |
| Final check-mcp.sh after adding five cases | Passing current regression/compatibility suite | PASS: 566 tests; Ruff lint/format131 files; mypy73 source files | Delegated end-to-end, real-role or deployed acceptance |
| Java17 focused existing/native compatibility selection | Selected reactor tests pass | PASS: 30 tests in12 suites, zero failures/errors/skips; BUILD SUCCESS | Auth development's excluded new framework, AccessServlet delegation, full native package or runtime acceptance |

New reproducible proof source:
`services/mcp/tests/integration/test_remaining_migration_gates.py`.
Principal/OBO/HTTP/storage are synthetic; actual SDK registration, operation
facades, contracts, capture/read workflow and error presentation are exercised.
The file was formatted after its initial five passes; no failed assertion or
fixture was adjusted. No production source changed to obtain a passing result.

Commands (from services/mcp):

```sh
uv sync --locked
../../scripts/check-mcp.sh
uv run --no-sync pytest tests/integration/test_remaining_migration_gates.py -q --junitxml=../../deployment/artifacts/tool-proof-2026-10-21/public-gates.xml
uv run --no-sync pytest ../../docs/mcp/existing-api-migration/attachment_readiness_proof.py -q
```

The last command ran once, unchanged, and failed collection. No PYTHONPATH/import
adjustment, fixture edit, retry or implementation repair was used. It remains a
separate failed readiness invocation outside normal regressions.

Java command (repository root):

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@17 mvn -f apps/sakai/pom.xml -pl webapi,announcement/announcement-tool/tool,entitybroker/core-providers -am '-Dtest=Mcp*Test,Existing*Test,LoginControllerTests' -Dsurefire.failIfNoSpecifiedTests=false test
```

Logs/XML and hashes are retained in the ignored checkpoint and machine results.
No package/release build or security-scan claim follows from this test selection.

## Current callers and independent research

Production source search finds context calls only in T09 registration and T20's
later `GradingWorkflow._prepare_mcq` path. T14/T15/T18 call HTTP GradingWrites and
require current metadata/submission observation revisions; they no longer consume
T09's native semantic hash. Current coverage/browser descriptions were stale and
are corrected; dated implementation evidence is unchanged.

T20 checks manifest completeness before any context read, then artifact integrity,
current context and complete stable roster pages before evaluation. The evaluator
also requires matching assignment configuration_revision, maximum, complete
context and supported.prepare. The retained T09 facade forces prepare false.
That later blocker is source-confirmed at grading.py:60 and evaluator.py:44–54;
it was not exercised by manufacturing a complete manifest or bypassing gates.
Thus closure needs a coordinated truthful context/provenance transition as well
as complete authorized roster and content. No evaluator or gate was weakened.

A14 source review reconfirms the raw Assignment helper at
AssignmentEntityProvider.getAssignDataForAnnouncement: it pushes an asn.new
SecurityAdvisor before retrieving/returning the raw Assignment. The model contains
scaleFactor, releaseGrades and properties, whereas SimpleAssignment computes
only display maximum from an effective scale. This route remains an unadopted
candidate requiring serialization, relationship/over-fetch and native role proof;
it is not a certified strict-context source for grade-only TAs. No request to it,
new auth allowlist or native business change was made. Existing native grading-list
release cells concern submission release, not the Assignment release flag.

## Authentication handoff and separate failure categories

- Historical positive delegated download: FAIL, expected200/actual403 before
  RequestFilter, binder or AccessServlet. This does not establish academic ACL
  denial. The historical two AccessServlet/content component passes use synthetic
  collaborators and remain component evidence only.
- Current Python readiness: harness/import ERROR with zero tests, not an auth,
  authorization or tool-behavior result. A separate future corrective step may
  address collection; it was not repaired in this pass.
- Missing new native auth module/filter registrations are intentional extraction
  facts here. No auth Java proof was rerun in or imported from auth development.
- Auth workstream must provide a separately assembled compatible integration,
  narrow content credential reach and correct filter/session chain, then establish
  target reach, identity isolation and cleanup. The unchanged Python flow protocol
  remains pinned by role.json (SHA d5f8d01f58d56be77a06647f09ecf9be00a5188addd0916a80307012eb765aa0).
- Tool/content workstream still needs source-bound MIME/length/full-byte/hash and
  redirect/filter/sendfile policy proofs after reach is available. Real-role ACLs,
  concurrent users and live storage/filter configuration remain unproven.

## Totals and next gates

20/22 local actual defaults replaced; T09/T20 remain. 22/23 historical native
business routes retired, only grading-context active; no resource family fully
migrated. These are source routing counts, not functionality or live acceptance.

Next independent migration gate: prove a safe existing field source for the strict
T09 context by role, including scale/release state and observed revision semantics;
resolve the later prepare capability/provenance coupling without inventing state.
T20 additionally requires a complete eligible roster with stable native identities
and certified source bytes. Generic visible membership totals or display-name
joins cannot close that gate. Auth chain/harness corrections must be separate
steps. D3 concurrency/CAS limitations, D6 durable backend/legacy ownership and D7
ordinary-UI/domain retirement remain. No deployment, activation, runtime/Azure
change, live academic operation, record/schema cleanup or uncertain-write replay.
