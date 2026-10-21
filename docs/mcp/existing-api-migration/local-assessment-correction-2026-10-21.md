# Client assessment correction — 21 October 2026

## Authority, starting state and preservation

The user explicitly requested removal of the server MCQ tool, use of proper grade-submission tools and a compact Skill revision in which a checking script is merely one available assessment method. This is a new product correction following the previous failed proof pass, not retroactive acceptance of that attempt.

Reverified only the tool-development checkout: branch `codex/tool-migration-development`, starting HEAD `3c572178edfd78a3f25ac156afc64384c73fa75a`, no tracked/index changes, one preexisting untracked `docs/mcp/existing-api-migration/__pycache__/`. The four worktree mappings matched the recorded separation; no other checkout was edited. Initial `python3 docs/mcp/existing-api-migration/check_scope.py --verify-progress` passed22 tools/five resources/one active native route. Predecessor and private checkpoint hashes were verified. A read-back-verified owner-only checkpoint preserves211 tracked files plus installed Skill bytes at `deployment/artifacts/local-grading-correction-2026-10-21/`. No historical manifests, evaluator/report/catalog fixtures, archives or continuation records were rewritten. Editor/cache files were preserved.

## Research and implementation

Reviewed the canonical migration plan and current worktree/role/preservation records, integration and grading designs, current tool/coverage/limitations/native/browser records, previous remaining-tool proof source/logs, actual public registrations, grading payload/write/journal/readback implementations, capture/proposal/resource handlers, SDK protocol tests and repository/installed Skill. The earlier attachment audit/results and readiness sources remain authoritative failure evidence; no new servlet/filter proof or readiness rerun occurred here.

The actual runtime chain was `mcp/tools.py → GradingWorkflow.prepare_mcq → complete capture/roster observations → evaluate_mcq → GradingOperations.create_proposal → Captures.create_proposal`. Removed the public registration, whole preparation/evaluation workflow and both proposal-creation methods. No runtime workflow imports the evaluator now. Frozen evaluator source, report rendering and exact provenance tests remain for historical verification; their preservation is not a server grading capability. The unused evaluator-observation contract remains inert, with no runtime callers. New source cannot create server MCQ proposals through a tool or these methods.

Retained `get_assignment_grading_proposal`, stored-record authorization/expiry checks and proposal/report resource reads for existing records. This is explicit read compatibility, not required for new assessment. No native-format records were imported or erased, and native historical storage is not automatically readable by the external-record reader. Cleanup/retention changes require a separate decision.

The needed tools already exist: `prepare_assignment_grade_payload` hashes/advisory-validates explicit approved rows, `save_assignment_grades` saves without return, `release_assignment_grades` returns separately approved saved grades, and grade/operation readers reconcile. None requires an MCQ proposal ID. Actual production path is public tool → typed grading operation → GradingWrites → existing Direct grade_form and native list/detail/edit observations → external operation journal. No business endpoint, authentication or protocol change was introduced.

Writes remain one submitted individual, integer displayed points, English forms, no Gradebook link, supported plain side fields and configured conditional journal storage. There is no native CAS, atomic multi-request transaction or causation guarantee. Successful local receipts remain `partial` with observation warnings. Broad historical input schemas do not establish bulk or decimal support.

The Skill now chooses direct answer-key checks, supplied tests, an optional assignment-specific workspace script, permitted rubric-based AI or human review. If useful, a script belongs inside the user's selected folder/workspace and is checked against known examples. Original evidence, authoritative ID mappings, hashes and unresolved/null scores remain protected. Student code execution still needs a separately approved isolated runner. Corrected stale native row-lock/storage/Gradebook synchronization claims. Repository and installed Skill's three files are identical; no unrelated installed files were changed.

## Files and host boundary

Current ResourceLink/EmbeddedResource delivery is not local-file materialization. Inspected the actual presenters/resource readers and CLI executable location; the installed CLI is a bundled binary, not available client source establishing a byte-to-file adapter. [Official MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) documents MCP connectivity but did not establish automatic byte-preserving workspace writes for these Sakai resources. No such acceptance is claimed. Existing SDK tests establish serialization/recovery within their tested protocol clients only.

The reference therefore requires a verified host file capability plus size/SHA-256 comparison if local processing is selected, without adding another login/importer, token handling or pretending the server can write the client's disk. Missing host file delivery is an explicit remaining acceptance gate. Current migrated attachment ACL/MIME/source-binding/integrity behavior is still unsupported; inline HTML capture does not substitute for a TXT attachment. Complete selected evidence is required for scoring; incomplete rosters cannot establish missing/zero rows.

## Fresh verification, expected and actual

Command, from `services/mcp`: `uv sync --locked`, then `../../scripts/check-mcp.sh` (output retained in the private `check-mcp.log`). The source was frozen after this run; no failing assertion, fixture, import or implementation was adjusted to obtain another result.

| Check | Expected | Actual and limit |
| --- | --- | --- |
| Ruff lint/format, mypy | Pass | Pass;137 formatted files,76 typed source files |
| Full Python regression | All tests pass against intentional catalog change | **583 passed,2 failed**; two unchanged `tests/protocol/test_grading_tools.py::test_independent_catalog_gates` cases expect19/22; actual18/21. Tool discovery/count-contract failures, not auth/authorization failures. Recorded without correction. |
| New public SDK grading proof | Explicit local scores validate, save, return, receipt/readback; no MCQ or custom route | Passed within full run. `test_public_explicit_payload_save_return_and_readback`: real public tool functions and Python workflows over synthetic existing-HTTP/storage. Validation sends no grade write; save and return each send once; receipt remains partial; score/return readback verified. No native servlet, live academic record, real role or concurrent-user acceptance. |
| Retired tool negative proof | Absent and cannot trigger reads/writes | Passed within full run; synthetic public registration/call path. |
| Legacy report access | Existing record stays readable without creating a proposal | Both SDK protocol modes passed with a preseeded synthetic record; zero private proposal writes. Does not prove deployed native-format migration. |
| Historical evaluator/catalog/report bytes | Unchanged | Compatibility/fingerprint tests passed; new explicit `local-assessment-catalog-v2.json` removal amendment preserves other names/descriptions/schemas and default gates. |
| Skill quick validator | Validate Skill | **Harness import error**: `python3 .../skill-creator/scripts/quick_validate.py skills/sakai-assignment-grading` failed at `import yaml`: `ModuleNotFoundError`. No validator checks ran; no installation/import repair attempted. |
| Repository guidance and diff whitespace | Pass | Passed; final scope/development-line verification recorded in the chained record. |

Before the test run, one editing command used a repository-relative path from the service working directory and errored with FileNotFoundError; it made no edit. The intended edit was applied from the correct directory before any test execution. This was an editing/setup error, not a Sakai proof.

The prior17 failures remain preserved in `remaining-tools-results-2026-10-21.json` and its private log. This separately authorized correction adapts their obsolete journal sender fixture into an explicit synthetic journal seam, and replaces removed-MCQ protocol scenarios with legacy-record reads plus independent explicit-grade payload checks. Those passing component tests do not become actual-HTTP write proofs; the separate new SDK/HTTP proof supplies that bounded routing evidence. No previous failure result was rewritten.

## Migration and acceptance state

Catalog5/8/18/21 and five resources;21 current public facades route to existing HTTP/external records, with20 earlier locally validated replacements and T09's full regression/compatibility gate still open. The removed MCQ tool is a product retirement, not an accepted replacement. Historical native retirement stays22/23; the now-uncalled grading-context route remains retained pending compatibility/regression review. No native source changed in this correction.

Separate auth development owns exact per-webapp/filter/route reach, delegated context/session isolation and protocol integration. Existing transports attach the OBO token on each downstream request; that does not prove every endpoint reaches its intended handler. The Python flow protocol file/hash and native wiring remain unchanged. A separately assembled matching auth integration is still required; no endpoint allowlist, filter order, credential guard or auth-development worktree was changed.

Historical positive attachment download still failed403 before RequestFilter/AccessServlet; it is not a downstream ACL denial. Synthetic actual-AccessServlet delivery/denial tests remain separate. Historical Python readiness import failed on `tests`; no readiness probes ran. Real-role permissions, source binding, concurrent-user isolation, delegated end-to-end byte integrity and intended-CLI file materialization remain unproven. Nothing was deployed, enabled or written to live academic records.

Next concrete corrective gate: separately update the two recorded catalog-count expectations to the explicit product amendment, then rerun full regression. Next acceptance gate: assemble matching auth integration and prove exact existing-handler reach/roles plus intended CLI resource-to-file fidelity. Attachment support and broader grading writes require separate source-backed work; do not bypass these gates by changing Skill wording or fabricating completeness.
