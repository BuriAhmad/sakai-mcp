# Attachment proof audit — 20 October 2026

**Overall result: NOT PROVEN / NOT ACCEPTED.** The user explicitly requested that
any failing proof/test be recorded without fixing it. No failing probe, production
implementation, permission check, route registration or runtime setting was repaired.
No content route was enabled; counts remain 20/22 local default replacements and
22/23 historical native business routes retired. Nothing was deployed.

## Results

| Check | Result | Exact meaning |
| --- | --- | --- |
| Actual AccessServlet dispatch → actual native content handler | PASS, one test | Exact fixture bytes and native MIME delivered with synthetic preselected session/resource/ACL/storage collaborators. |
| Actual servlet handling native content denial | PASS, one test | Native callback denial produces HTTP403 and no bytes. This tests mapping/enforcement, not effective role computation. |
| Positive delegated credential guard → RequestFilter → binder → servlet/content | FAIL, one test | Expected200, actual403, `reached=false`. Current guard rejects the content context before native RequestFilter/binder/AccessServlet executes. |
| Separate Python positive readiness probes | COLLECTION ERROR | `ModuleNotFoundError: No module named 'tests'`; zero probe tests executed. No capability conclusion from those three probes. |
| Access servlet auth registration | MISSING source prerequisite | XML mappings are oauth.pre → sakai.request → oauth.post. No mcp.credentials/mcp.session registration. Read-only source observation, not a passing Python probe. |
| Instructor/student/outsider/revoked/scoped-TA effective permissions | BLOCKED | Delegated chain did not reach native target; real native role/config/data acceptance not performed. |
| Selected-source binding, arbitrary/cross-course reference denial, before/after source change | BLOCKED | Public content route remains unaccepted. Not proved through a delegated download. |
| MIME/length/hash, truncation/redirect/sendfile enforcement in delegated download | BLOCKED | Existing handler characterization is useful but does not close end-to-end response enforcement. |
| Concurrent content identities and cleanup | BLOCKED | Target context rejected before binding. Other-context regressions are not proof for Access. |
| Live deployed configuration, role and storage/filter acceptance | NOT RUN | No live tokens, resource reads, feature/runtime changes or academic operations. |

Machine-readable results and exact probe hashes:
[attachment-audit-results-2026-10-20.json](attachment-audit-results-2026-10-20.json).
A blocked case is not a pass. A Python collection error is a harness failure, not
a demonstrated application capability failure.

## What was actually exercised

`AccessServletProof.NativeFixture` uses the original `AccessServlet.dispatch`,
which resolves a native EntityProducer/HttpAccess and invokes the unchanged
`BaseContentService.handleAccessResource` using the existing synthetic content
fixture. Session, parser, entity lookup, ACL decision and storage are synthetic.
This is a local component proof; ordinary BasicAuth `doGet`, effective native ACL
calculation and rendered/deployed behavior are not thereby established.

`AttachmentReachProof` reuses the existing configured auth regression fixture,
constructs the actual native RequestFilter/binder and servlet/content target, and
sends a synthetic bearer GET for an attachment in `/access`. Its positive assertion
fails403 with target not reached. Verifier/account fixtures are synthetic; this is
not a real-token acceptance test. No source changes were made to bypass the guard
or force the native target to run after that rejection.

The Java audit was run once; the failed positive assertion remains untouched.
The Python proof was run once with the invocation below; its source, invocation
and import error remain unchanged. No adjusted PYTHONPATH/retry was used to repair
collection. Downstream assertions in that uncollected module are unexecuted probes,
not accepted byte/source/registration evidence.

## Reproduction

Java, repository root (expected nonzero because the positive delegated proof fails):

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@17 mvn -f apps/sakai/pom.xml -pl webapi,mcp-auth -am \
  '-Dtest=AccessServletProof,AttachmentReachProof#delegatedContentMustReachNativeServletChain' \
  -Dsurefire.failIfNoSpecifiedTests=false test
```

Python, from `services/mcp` (recorded collection error):

```sh
uv run --no-sync pytest ../../docs/mcp/existing-api-migration/attachment_readiness_proof.py \
  -q --junitxml=/tmp/sakai-attachment-audit-python-positive.xml
```

The explicit Java classes end in `Proof`; the Python probe lives outside the
normal service test selection. This keeps readiness evidence separate from
regressions that assert the intentional current rejection. They were not renamed,
skipped or changed after failure to manufacture passing readiness results.

Logs: `/tmp/sakai-attachment-audit-positive.log`,
`/tmp/sakai-attachment-audit-python-positive.log`. Exact native JUnit XML and both
logs are privately copied and hashed in this continuation's owner-private checkpoint.

## Independent regression and preservation checks

- Fresh locked sync and `check-mcp.sh`: **568 Python regression tests passed**,
  Ruff lint/format over131 files, mypy73 source files. Frozen public contracts,
  catalogs/descriptions, evaluator and report baselines unchanged.
- Fresh explicit Java17 normal focused selection: **48 regression tests in nine
  suites passed**, zero failures/errors/skips. Nine content characterization cases,
  denial guard, grading/wiring and auth/Sites/Portal/Login checks remain passing.
- These passing selections do not include or override the failed positive proof:
  the separate Java audit has **two passes and one failure**. The separate Python
  audit has **one collection error and zero executed tests**.
- Test-only Access/Velocity dependencies and reusable synthetic fixture bridges
  were added. No native/Python production implementation bytes changed from the
  fresh audit checkpoint. Runtime auth dependency allowlist still passes.
- No package rebuild/deployment claim in this audit; previous package verification
  remains historical. No production class/source retirement here.
- Required scope/progress/chained preservation, guidance and whitespace checks pass.
  Fresh owner-private checkpoint: 76 manifest paths,72 archived source files, four
  editor fingerprints excluded and preserved. Prior manifests/archives/continuations
  unchanged; new continuation pins the attachment-proof predecessor.
- Migration branch/HEAD remain `codex/replace-custom-sakai-api` /
  `0f9f44a76f34777b52f56ae03634ffd3a0b3bc6c`; main/custom remain
  `208d69ac624910a29a7529934ddcc18bbac853e8`. Independent custom worktree is clean;
  index empty. No reset/clean/stage/push/Git reorganization, schema/stored-record
  deletion, runtime/Azure action or academic operation.

## Unresolved gate

The full proof has stopped at the rejected delegated content boundary. Native
servlet component success does not establish a usable or safe delegated attachment
workflow. Fixes to credential reach/registration, harness collection and downstream
implementation/acceptance are intentionally deferred under the user's instruction.
Keep the content route blocked and preserve all failed/blocked outcomes for review.
