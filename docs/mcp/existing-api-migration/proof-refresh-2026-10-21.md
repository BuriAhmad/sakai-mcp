# Fresh local proofs after catalog correction — 21 October 2026

## Scope, source and preservation

The user authorized updating the two outdated catalog assertions and rerunning proofs, with failures recorded without repair and proposed fixes reported separately. The only test/source edit is `services/mcp/tests/protocol/test_grading_tools.py`: grading-only19→18, combined22→21. Default5/setup8 expectations, tool definitions, descriptions/schemas and frozen fixtures remain unchanged. Correction commit: `7cfa3204fdc1dd5e68e637ba9ada400059d013fa`. All proof runs below used that source; no proof, fixture, import, assertion or implementation was changed after execution.

Verified branch `codex/tool-migration-development`, starting HEAD `de7158bf4e97d3e10f3cdef220a7783cd07849a4`, empty index/clean tracked tree, preexisting untracked migration `__pycache__`, and all four worktree mappings. Only the specified tool worktree was used. Initial scope/progress check passed. Verified predecessor/private hashes and preserved213 tracked files in a fresh read-back-verified owner-private archive under `deployment/artifacts/proof-refresh-2026-10-21/`. Historical results/archives/manifests/continuations remain unchanged; new results are [proof-refresh-results-2026-10-21.json](proof-refresh-results-2026-10-21.json).

## Expected versus actual

| Case | Expected | Actual | Reached components / limits / owner |
| --- | --- | --- | --- |
| Full Python regression | All current normal tests pass with5/8/18/21 catalog | **585 passed**, no failures; exit0 | Actual SDK tools/workflows/parsers/transport over synthetic OBO, HTTP and storage. Includes explicit score payload/save/return/readback, removed-MCQ negative call, resource protocol roundtrips, legacy report readers and observation/journal gates. Does not establish native servlet/delegation, real roles, host file delivery or live writes. Tool development. |
| Ruff and mypy | Pass | Lint/format pass137 files; types pass76 source files | Static service checks, no live/runtime acceptance. Tool development. |
| Native Java17 focused selection | Selected suites pass | **31 tests,13 suites**, zero failure/error/skip; BUILD SUCCESS, exit0 | Existing announcement/pages/site visibility and raw model/actual JSONTranscoder proof, retained native wiring/services/legacy bearer/JWT and login regressions. Synthetic collaborators; not the excluded new auth framework, AccessServlet chain, real role matrix or full package/release. Tool/native compatibility. |
| Positive Python attachment readiness | Three probes execute and pass | **Collection error**, exit2: `ModuleNotFoundError: No module named 'tests'`; **zero probes executed** | Imports stopped before filter-registration, content or public-resource assertions. Harness error, not authorization denial or tool behavior failure. Tool proof harness. |
| Skill quick validator | Skill checks execute | **Import error**, exit1: `ModuleNotFoundError: No module named 'yaml'`; **zero validator checks** | Python dependency missing before validation. Skill validation harness. |
| Delegated positive AccessServlet proof | HTTP200; native chain reached | **Not rerun: source unavailable in this line** | `apps/sakai/mcp-auth` and both historical AccessServletProof/AttachmentReachProof classes are absent as designed. No auth files copied, no other worktree build performed. Historical result remains FAIL403, reached=false before RequestFilter/binder/AccessServlet. Auth development/integration owns next run. |
| Access filter registration | Matching delegated credential/session integration | **Missing source prerequisite**, fresh XML inspection only | Mappings remain oauth.pre → sakai.request → oauth.post; matching MCP credential/session mappings absent. This is not an executed readiness probe or ACL decision. Separate auth integration. |
| Intended CLI resource-to-workspace file delivery | Exact selected bytes saved and size/hash verified | **Not exercised / unproven** | SDK text/blob roundtrips passed in normal tests; they do not prove host filesystem materialization. No automated intended-client file-delivery proof exists in this source line; no live academic content downloaded. Host/tool acceptance. |
| Effective role permissions, selected-source binding, concurrent-user isolation, delegated MIME/length/hash integrity | Positive and negative matrix accepted through actual target chain | **Still unproven / blocked** | No separately assembled matching auth integration or authorized live/native-role dataset/host acceptance run. Historical component successes cannot close these gates. Auth plus tool/native-role acceptance. |

Raw Java XML was copied from the four selected modules after the run and summed by suite names present in this run's log, avoiding stale unrelated Maven reports. Exact logs/XML/source hashes and private paths are indexed by the new results and chained development-line record.

## Commands

From `services/mcp`:

```sh
uv sync --locked
../../scripts/check-mcp.sh
uv run --no-sync pytest ../../docs/mcp/existing-api-migration/attachment_readiness_proof.py -q --junitxml=../../deployment/artifacts/proof-refresh-2026-10-21/attachment-readiness.xml
```

From the worktree root:

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@17 mvn -f apps/sakai/pom.xml -pl webapi,announcement/announcement-tool/tool,entitybroker/core-providers,assignment/tool -am '-Dtest=Mcp*Test,Existing*Test,LoginControllerTests,ExistingRawContextProof' -Dsurefire.failIfNoSpecifiedTests=false test
python3 /Users/burhanahmadkhan/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/sakai-assignment-grading
python3 docs/mcp/existing-api-migration/check_scope.py --verify-progress
python3 docs/mcp/development-lines/verify_arrangement.py --current
./scripts/check-repo-context.sh
git diff --check
```

The two unsuccessful readiness/validator commands ran once each, unchanged. No adjusted PYTHONPATH, `python -m pytest`, dependency installation, assertion/fixture modification or production repair followed either error. No auth/filter registration, credential guard, allowlist, token/OBO/session integration, native business behavior, deployment/runtime state or academic record was changed.

## Proposed corrective work — not implemented

1. **Readiness harness:** make service test fixtures importable in a separately authorized harness correction. A candidate is `uv run --no-sync python -m pytest` from `services/mcp` (or locating these probes within the service test package). Preserve the current collection error, rerun all three probes without weakening assertions, and treat any newly exposed capability failure independently. This proposed invocation has not been tried here.
2. **Validator harness:** run the unchanged skill validator in an isolated validation environment containing PyYAML. No production dependency, global package installation or Skill change is needed merely to load this validator. This remains a proposal.
3. **Delegated chain:** in auth development/integration, assemble a compatible auth version and prove narrow required existing routes in each relevant web application with correct filter order, identity/session binding and cleanup. Then rerun the positive AccessServlet chain and negative/ordinary-login cases. Do not infer success from an unrelated endpoint or broaden root access merely to pass a test.
4. **Attachment tool behavior:** even after auth succeeds, current `ExistingApiTransport` descriptor and public `GradingOperations.read_grading_file` deliberately reject unsupported content/attachments. A separate source-backed tool change must bind each selected reference to fresh authorized submission evidence and enforce tested MIME, byte length/integrity, redirect/sendfile/filter behavior and source changes. Auth success alone cannot make these adapter gates pass. Do not just remove the unsupported guards.
5. **Workspace delivery and acceptance:** prove the intended CLI's existing authenticated resource connection can hand original text/blob bytes to a local file writer without model reconstruction; verify size/hash and authoritative identity mapping. If the host lacks that bridge, design a small credential-free host handoff. Then run real-role, cross-source, revoked-user and concurrent-user acceptance before claiming general attachment support.

## Current status

All21 current public facades route to existing HTTP/external records; server MCQ preparation remains intentionally retired. The former catalog regression gate is closed by fresh585-test normal verification. This is not full functional/live acceptance: context remains a narrow instructor subset; resource/roster completeness and unsupported attachment/write variants stay explicit. Native retirement remains22/23, one uncalled grading-context route retained pending separate native/client compatibility and focused retirement review. No new route retirement occurred. Single-individual/integer/English-form/unlinked grading limits and advisory, non-CAS observations remain.

The Python client flow protocol/hash and native auth wiring remain unchanged. This tool-only native tree does not provide the matching server auth integration. Prior17-test and2-count-test failures, attachment403 and import errors remain historically recorded; fresh normal passes do not rewrite their outcomes. No live deployment or activation occurred.
