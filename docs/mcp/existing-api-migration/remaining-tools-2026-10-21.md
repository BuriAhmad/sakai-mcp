# Remaining-tool implementation attempt — 21 October 2026

**Local implementation with an open regression gate. Not a release or completed
migration.** No auth/filter/protocol code, frozen public contracts, evaluator or
report baselines changed. No deployment, live reads/writes or runtime action.

## Starting state and preservation

Verified branch codex/tool-migration-development, HEAD36716ee198001d9ab98c679958b6efe3fc90bce3;
tracked source/index clean, only the prior generated readiness __pycache__ untracked.
The four-worktree mapping matches the recorded arrangement. No other checkout was
modified. Root/scoped rules, maintained plan and prior proof/preservation records
remain applicable; initial --verify-progress passes.

Before edits, archived207 tracked migration paths under the owner-private ignored
`deployment/artifacts/remaining-tools-2026-10-21/`, read back every archive member
against its SHA256, and pinned the prior proof record. No credentials/runtime data
were copied. The new development-line record chains the earlier proof without
rewriting any baseline/archive/manifest/continuation. New source after the full
failed run is fingerprinted in failed-run-snapshot.json and remains unchanged.

## T09 actual default replacement

The public SDK registration -> invoke_grading -> GradingOperations context now
calls GradingContextReads. It verifies actor/course and site-wide asn.grade,
asn.new, asn.revise and gradebook.editAssignments before A14. Existing native
positive individual grading-list/detail and supported edit observations precede
GET /direct/assignment/annc/{site}/{assignment}.json. No messageId/query is sent.
The native helper/permission advisor is unchanged; its raw relationships are an
explicit bounded instructor over-fetch, never a way to bootstrap draft/group/
anonymous/grade-only TA access. Actual role entitlement and lazy relationship
serialization must still be verified under matched native auth.

Raw fields are strictly parsed: IDs/context, scale, maximum, release/deleted/draft/
group flags, peer/content-review flags, groups/attachments, title/instructions,
property map and dates. Required omissions/null/type coercion do not become false
or zero. Nonempty Assignment attachments/groups and other unsupported variants
fail. Exact finite point subset requires power-of-ten scale up to1e9, compared
against the existing DTO display maximum. The raw codec's enum representation has
only declaringClass, so it cannot establish the enum value; selected DTO/edit
observations supply the supported grade/submission kinds. Raw Instant epochSecond
and nano are emitted as UTC RFC3339, preserving nanoseconds.

The unchanged public shape has distinct httpctx1 observation revisions; these do
not replace HTTP write preconditions or promise CAS. Current roster counts remain
null, completeness false, independent Gradebook link unknown/unavailable and
prepare/save/release false. Private submission relationships are not retained in
the parser/output/configuration hash. Unknown/full-field/role acceptance is not
closed by this useful partial context. No legacy route fallback remains.

## T20 independent migration work

GradingWorkflow no longer calls the native/public T09 context. Owner-bound proposal
reconciliation and complete site-scope export gates remain first. It still checks
artifact length/hash, complete stable site-scope roster pages,500-row limit and
cursor loops. After those gates, current existing source rows must match roster
content revisions/IDs; existing edit-form restrictions and strictly observed
point/access/group metadata produce only the fields consumed by the unchanged
evaluator. It does not invent raw scale/release state or construct a fake public
T09 object. Its internal metadata coverage marker is separate from native academic
state; complete roster/content must already have been established independently.

Current captures and roster pages remain incomplete and therefore fail before
these later stages. Successful current-source MCQ preparation is **not established**.
The later path is component-tested for metadata rejection, not a complete delegated
evaluation proof. Attachment/eligible roster closure is still mandatory. No
current partial capture, fixture capture record or native state was relabelled
complete. Existing frozen proposals can still reconcile/read as before.

## Proofs and regressions

| Check | Expected | Actual | Scope/owner |
| --- | --- | --- | --- |
| Native raw-model/EntityBroker JSONTranscoder | Required raw scale/release/properties/date fields serialize | PASS:1 JUnit test; rerun to capture wire shape also1 pass | Actual existing model/codec with synthetic object; not provider permissions, effective native roles or delegated servlet acceptance; tool proof |
| New context facade and selected SDK/legacy gating tests | Existing-route output, denied/unknown/mismatched fields fail, no private output/custom fallback | PASS:21 tests | Actual Python facades and SDK; synthetic HTTP/principal/OBO/store |
| Full service check after migration attempt | All tests pass with frozen contracts intact | FAIL:567 pass,17 fail; lint/format137 files and mypy76 files pass | Full compatibility gate OPEN |
| Fifteen receipt-test cases | Fixtures continue to construct simulated historical writer | ERROR/FAIL:AttributeError at fixture reference to removed private _send | Test fixture/interface coupling; no native or academic request is reached in these failures |
| Two complete-proposal host cases | Fake client supports full workflow | FAIL:host tool returns error; traceback identifies fake GradingClient lacking submissions | Fake-client setup/interface gap inside exercised SDK/host path; not a native auth denial |
| Required scope/development-line/guidance checks | Inventory/source chain preserved | See final-verification.log; does not override failed tests | Source preservation only |
| Historical positive attachment readiness/delegated chain | Previously failed/error outcomes retained | Not rerun or repaired here | Harness error and pre-servlet403 remain separate auth/tool acceptance gates |

The initial commentary inference that the Java proof did not execute was incorrect:
“No tests” messages were earlier reactor modules; the final Assignment module's
Surefire output/XML records one executed passing test. No Java proof/harness fix
was required. The rerun added only synthetic wire-shape output after that pass.

The broad failed suite is preserved without source/fixture/assertion fixes after
failure. Context-specific obsolete tests were deliberately migrated before the
first run to exercise the new default; their old bytes remain in the checkpoint
and Git predecessor. The subsequently failing receipt/host fixtures are untouched.
No failing case was skipped, renamed away, reinterpreted as a pass or rerun green.

Commands, repository root unless indicated:

```sh
python3 docs/mcp/existing-api-migration/check_scope.py --verify-progress
JAVA_HOME=/opt/homebrew/opt/openjdk@17 mvn -f apps/sakai/pom.xml -pl assignment/tool -am -Dtest=ExistingRawContextProof -Dsurefire.failIfNoSpecifiedTests=false test
# services/mcp:
uv run --no-sync pytest tests/unit/sakai/test_http_context.py tests/integration/test_remaining_migration_gates.py tests/unit/sakai/test_grading.py -q --junitxml=../../deployment/artifacts/remaining-tools-2026-10-21/context-python.xml
../../scripts/check-mcp.sh
```

The shape-capture Java run uses the same Maven command; separate original and
shape logs are retained. No full native package/build acceptance is claimed.

## Authentication boundary and native retirement

A14's new caller requires separately reviewed matching delegated route/filter
integration. Existing tool-only native source does not supply it. No auth code,
endpoint credential allowlist, filter registration/order, OBO/token/session wiring
or pinned Python flow protocol changed. Source lack of matching auth is a dependency,
not an invitation to bypass it. Real A14 roles, raw relationship/lazy-load fidelity,
multiple identities and current deployment remain unproven. Attachment ACL, MIME,
byte integrity, selected source binding and concurrent-user proofs remain open.

No production Python /api/mcp/v1 route caller remains in inspected source, but the
native grading-context route is **still active**. Its retirement is deferred because
the broad regression gate failed and older clients still need compatibility
planning. The inventory now explicitly separates an uncalled retained compatibility
route from actual callers; the scope checker validates that every such entry is
active, unique, documented and not also claimed as a current caller. It does not
weaken native permissions or authorize retirement/deployment. All native query,
store/domain/schema/cleanup dependencies and academic records remain preserved.

Counts:21 actual default facades wired; the preceding20 validated replacements
retain their historical status. T09's full regression acceptance is open; T20
remains functionally incomplete. Native retirement remains22/23, one active route;
no resource family is newly complete. Do not report21 accepted or22 complete tools.

Next separate corrective step: update the receipt/host test doubles for the changed
interfaces, rerun all checks and review whether further behavior defects emerge.
This pass does not perform those corrections. Then consider focused last-route
retirement with compatibility/source preservation, plus separately assembled auth
and actual native-role proof. Complete eligible roster/content and D3/D6/D7/D8
acceptance remain. Nothing was pushed, deployed, enabled, cleaned or replayed.

## Exact failing cases

- `tests/protocol/test_grading_resources.py::test_complete_proposal_workflow_and_tools_only_host[legacy]`
- `tests/protocol/test_grading_resources.py::test_complete_proposal_workflow_and_tools_only_host[2026-07-28]`
- `tests/unit/sakai/test_grading_operations.py::test_confirmed_partial_is_external_and_repeat_never_sends`
- `tests/unit/sakai/test_grading_operations.py::test_receipt_failures_never_read_legacy_or_write[no-store]`
- `tests/unit/sakai/test_grading_operations.py::test_receipt_failures_never_read_legacy_or_write[permission]`
- `tests/unit/sakai/test_grading_operations.py::test_receipt_failures_never_read_legacy_or_write[identity]`
- `tests/unit/sakai/test_grading_operations.py::test_receipt_failures_never_read_legacy_or_write[target]`
- `tests/unit/sakai/test_grading_operations.py::test_receipt_failures_never_read_legacy_or_write[corrupt]`
- `tests/unit/sakai/test_grading_operations.py::test_receipt_failures_never_read_legacy_or_write[hash]`
- `tests/unit/sakai/test_grading_operations.py::test_receipt_failures_never_read_legacy_or_write[missing]`
- `tests/unit/sakai/test_grading_operations.py::test_request_id_collision_and_persistence_failure_never_send`
- `tests/unit/sakai/test_grading_operations.py::test_two_workers_only_send_once_and_receipt_reply_failure_stays_unknown`
- `tests/unit/sakai/test_grading_operations.py::test_release_uses_same_journal_and_no_store_commit_has_no_http`
- `tests/unit/sakai/test_grading_operations.py::test_record_binding_expiry_and_warning_contract_fail_closed[expired]`
- `tests/unit/sakai/test_grading_operations.py::test_record_binding_expiry_and_warning_contract_fail_closed[owner]`
- `tests/unit/sakai/test_grading_operations.py::test_record_binding_expiry_and_warning_contract_fail_closed[provenance]`
- `tests/unit/sakai/test_grading_operations.py::test_record_binding_expiry_and_warning_contract_fail_closed[warning-budget]`
