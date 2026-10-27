# T09/T18 grading-context and payload review — 20 October 2026

This is a source review of the next grading migration dependency group. No public
routing, schema, evaluator, description, native handler, feature gate or runtime
state changed. Neither tool is counted as replaced.

## Public caller chain

- `get_assignment_grading_context` is registered in
  `services/mcp/src/sakai_mcp/mcp/tools.py` and calls
  `GradingOperations.get_assignment_grading_context` in
  `services/mcp/src/sakai_mcp/sakai/grading.py`. Its presenter preserves the
  strict `ContextResult` contract from `contracts/grading_native.py`.
- `prepare_assignment_grade_payload` is registered in the same public module and
  calls `GradingWorkflow.prepare_grade_payload` in
  `services/mcp/src/sakai_mcp/workflows/grading.py`.
- The preparation workflow hashes the canonical request and calls the active
  native `save_assignment_grades` or `release_assignment_grades` method with
  `mode="validate"`. The native result is returned alongside unchanged commit
  arguments. This mode does not perform an academic commit, but it does execute
  native preflight.
- `save_assignment_grades` and `release_assignment_grades` still call native
  routes. Their Java `McpGradeMutationService.write` invokes the shared
  `McpGradingEvidence.revision`, `current`, permission, selected-target, score,
  feedback and state checks. Operation records are still native-owned.

## Existing HTTP evidence and strict fields

The migrated submitted-row path establishes a current actor/site/grade
relationship and reads `/direct/assignment/item`. Its `AssignmentMetadata` parser
requires an observed subset: IDs/site/title, draft, grade scale, submission type,
points (nullable), some group/anonymity/resubmission settings, and open/due/close
time strings. It does not provide every required `GetAssignmentGradingContextResult`
field, including a certified native release flag, all integration capabilities,
deleted state, and the full association property bag. The strict grading context
contract represents several of these as non-null booleans and has no unknown
state for them.

The existing setup edit form is permission-gated to Assignment editing and is
used only by the separate setup flow. Its observation cannot establish complete
context for a grade-only TA. Gradebook item-data and selected score display are
also separate projections and do not certify the missing Assignment settings.
No current live rendered form/delegated-role evidence closes these gaps.

## Revision compatibility

The remaining native context/mutation compatibility method
`McpAssessmentService.revision(Assignment)` hashes persisted Assignment content
and associations: title/instructions, draft/deleted, dates, points/scale/type,
audience/group and membership, release, peer/content-review/individual flags,
attachments, and all Assignment properties. Current HTTP metadata and setup-form
parsers do not expose all those inputs with equivalent semantics.

Python `http1-` revisions intentionally hash only their named observed projection.
They are not this native semantic hash, a database version, or a CAS token. Current
save/release routes compare the provided expected revision with the native
semantic hash, so a new context cannot safely hand them an `http1-` revision while
those routes remain the active commit path. Retaining the old context route merely
to obtain a revision would leave T09 dependent on the custom business API and is
not a default replacement.

## T18 validation meaning

The active native `mode="validate"` path does not grade or return submissions. It
nevertheless performs current native assignment authorization/revision checks,
resolves each exact submission, compares content and grade revisions, validates
score units/maxima and checks release/return state and Gradebook target policy.
The result contract reports an `OperationReceipt` with per-row `validated` stages.

The researched existing UI save/return forms have no dry-run validation action.
Removing the native call and returning a locally schema-valid payload would not
prove the same facts, and the frozen result/description has no explicit
schema-only status. Calling a native save/return form with a fake validation flag
would risk an academic write and is prohibited.

## Next gate

Preserve current public defaults and shared consumers. First either prove an
existing-HTTP source for every legacy semantic revision input or design a
compatible coordinated observation-revision cutover for T09, T18, T14 and T15
that keeps the exact approval boundary and makes stale observations/conflicts
explicit. Separately resolve D3 write concurrency/uncertain outcomes and D6
external durable operation ownership/retention/legacy import before migrating
mutation or operation receipts. Keep MCQ blocked on complete evidence. No native
business handler, data/schema cleanup, live operation or feature activation is
authorized by this review.

## Verification references

- `McpAssessmentService.java`: semantic Assignment revision inputs.
- `McpGradingEvidence.java`: current revision/submission preconditions.
- `McpGradeMutationService.java`: validation and commit behavior.
- `contracts/assignments.py` and `contracts/submissions.py`: existing HTTP
  Assignment metadata and submitted-row projection.
- `workflows/selected_grades.py`: selected readback permissions and revision.
- `workflows/grading.py`: current T18 native validation call and canonical hash.
- `grading_native.py`: frozen context, mutation, and receipt DTO contracts.

## Fresh local verification

- `uv sync --locked`: passed.
- `../../scripts/check-mcp.sh`: **535 tests passed**; Ruff lint passed, formatting passed for 123 files, and mypy passed for 70 source files.
- `./scripts/check-repo-context.sh`: passed.
- `git diff --check`: passed.
- `python3 docs/mcp/existing-api-migration/check_scope.py --verify-progress`: passed; 22 tools, five resources, four active native routes, 23 historical routes and frozen catalogs verified.
- Migration HEAD/branch remain `0f9f44a76f34777b52f56ae03634ffd3a0b3bc6c` / `codex/replace-custom-sakai-api`; the independent custom worktree remains clean at `208d69ac624910a29a7529934ddcc18bbac853e8`.
- No Java source changed in this increment, so no new Java package/test claim is made. No live acceptance, deployment, feature activation, runtime/Azure change, academic operation, or data cleanup occurred.
