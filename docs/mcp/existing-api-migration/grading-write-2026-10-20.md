# Existing HTTP grading writes and advisory preparation — 20 October 2026

Actual new default replacements: T14 `save_assignment_grades`, T15
`release_assignment_grades`, T18 `prepare_assignment_grade_payload`.
Current totals: **20/22 actual public defaults locally replaced; 22/23 historical
native business routes retired locally**. Only T09 grading context and T20 MCQ
preparation remain. None of five resource families is fully migrated. These counts
mean default routing replacement with disclosed functionality limits, not full
parity, real-role acceptance, configuration inventory or deployment.

## State and preservation

Fresh branch/ref checks: migration worktree `codex/replace-custom-sakai-api`, HEAD
`0f9f44a76f34777b52f56ae03634ffd3a0b3bc6c`; custom worktree remains clean at
`208d69ac624910a29a7529934ddcc18bbac853e8`, with main at that baseline. Index is
empty. No reset, clean, branch switch, stage, push or further Git reorganization.

Before editing, a fresh owner-private verified checkpoint was created at
`/Users/burhanahmadkhan/Downloads/Sakai-Grading-Write-2026-10-20`:
205 manifest paths, 201 archived source paths; four editor files were fingerprinted
and excluded from the archive. A new named continuation pins the preceding
operation-read record (`c8e59a8d14b4efa75da01abb775347acfe03c8eb1486a7ad2310bc9242c30c06`).
Prior continuations/manifests/archives and frozen contract/catalog/evaluator/report
baselines are unchanged. Archives were never extracted over the checkout.

## Public callers and implementation

The original SDK tool handlers call `GradingOperations.save_assignment_grades` and
`release_assignment_grades`, now directly backed by `GradingWrites.execute`.
`GradingWorkflow.prepare_grade_payload` retains the canonical serialization/hash
and exact approved commit arguments; its validate calls now reach read-only HTTP
preflight. No feature gate was changed or enabled. Neither mode uses a custom
save/release business route or fallback.

Focused modules:

- `workflows/grading_writes.py`: scope, current observations, supported state,
  revision preflight, durable one-send callback and partial readback.
- `contracts/grading_preservation.py`: native overwritten side-field checks.
- `workflows/grading_operations.py`: existing owner-bound Prepared/Sending/Returned
  journal and historical external receipt lookup. Prior record provenance remains
  compatible; repeated IDs never resume/replay, different payloads conflict.
- `contracts/submissions.py`: internal source-defined private notes, feedback text
  and properties. These are never copied to public grading models/reports.
- `sakai/existing_transport.py`: fixed URL-encoded grading action, isolated
  credential request, one attempt; no redirected/default-cookie/shared-auth request.

## Existing interface and authorization research

Source: `AssignmentEntityProvider.setGrade` in
`apps/sakai/assignment/tool/src/java/org/sakaiproject/assignment/entityproviders/AssignmentEntityProvider.java`;
`AssignmentToolUtils.gradeSubmission`, `scalePointGrade` and
`AssignmentServiceImpl.getGradeDisplay`; existing native Assignment list/edit
forms and `assignment-tool-list-submissions.vm` release cells.

The existing action is `POST /direct/assignment/setGrade.json`. It accepts
`courseId`, `siteId`, `gradableId`, `studentId`, `submissionId`, `grade`,
`gradeOption`, `privateNotes`, `feedbackText`, `feedbackComment`,
`resubmitNumber`, `resubmitDate`, `extensionDate`. It retains existing feedback
attachments via `GRADE_SUBMISSION_DONT_CLEAR_CURRENT_ATTACHMENTS`; no attachment,
rubric, caller-selected actor or session fields are sent. Native `save` differs
from `retract`; `return` sets returned/released and can notify through existing
behavior. Python neither changes nor suppresses native effects.

Existing `getSubmission`, `canGrade` and native handler permissions remain. Python
additionally establishes delegated current-user/site identity, site-wide grading,
posted individual target membership, editable Assignment and item-edit authority,
exact submission/student binding and observed native unreleased state. Every
reobservation is bound to the same actor. Group-only TA and unsupported mode reads
fail before hydration/mutation. This is an intentionally narrower instructor scope.

Only authentication credential reach changed in Java: the shared extension accepts
the exact selected Direct POST, REQUEST dispatch, no query/Transfer-Encoding,
positive bounded Content-Length, URL-encoded MIME, singleton fixed field allowlist,
required IDs/grade/action and `save`/`return` actions. It adds no business endpoint,
service, model, persistence, security advisor or permission bypass. Existing native
business authorization remains authoritative. Ordinary non-Bearer behavior remains
covered by focused chain/Login checks. Actual rendered/delegated role acceptance
remains outstanding; synthetic source-derived fixtures are not proof of a running
native grader with these fields or of notification delivery.

## Supported subset and honest preconditions

One submitted individual site-wide points row; English locale; integral displayed
score within observed metadata and native edit-form maximum; observed no Gradebook
integration (present enabled unchecked control, no multi-Gradebook widget). Unsupported
group/anonymous/peer/review/rubric/tag/calendar/attachment/policy variants reject
before mutation. No Gradebook score or projection success is asserted.

Private notes, feedback text/comment, resubmission count/date and extension date
must be observable and exactly preservable under the source handler's trimming,
formatting and Unicode rules. This subset accepts exact trimmed ASCII plain text
and bounded known numeric override representations. Missing properties, incomplete
resubmission override pairs, rich/unsafe/control/non-ASCII text fail before POST.
Feedback preserve/replace/clear are supported within this text subset. Submission
attachment bytes/completeness remain unresolved, even though this action retains
existing attachment references.

Assignment revision comes from the HTTP metadata projection in T19 `list_assignments`
or T16 `get_assignment_grades`. Content revision and grade revision come from T11;
the T16 grade/release composite is also explicitly checked against its current
projection. A fresh positive release observation is required independently. Already
returned/released rows reject. Release additionally checks current saved score,
graded flag and exact feedback digest. The T09 native semantic hash is **not**
accepted or substituted. Its retained strict full Assignment result cannot yet be
truthfully reconstructed through existing reads; its prepare/save/release hints
are false with explicit reason/warning directing callers to HTTP observations.

Validation has no academic POST or journal mutation and reserves nothing. Commit
requires a configured durable store before HTTP, records Prepared/Sending, freshly
rechecks actor/metadata/form/content/grade/private fields, then sends once. All
repeated operation IDs read historical records without resuming, including pending
intents. New IDs are new academic intents, not automatic recovery.

## Concurrency, effects and uncertainty

HTTP observations are not native locks/CAS/transactions. Another writer can change
state between the last read and POST. The native handler can persist several fields
and notify without an atomic external receipt. Readback checks actor/target,
metadata/form, score, graded/released/returned flags, content revision, preserved
side fields and all observed properties except source-defined `last_graded_date`.
It cannot prove complete unobserved state or causal authorship.

Successful commit always reports `outcome=partial`, observed stage `saved` or
`assignment_released`, observed revisions and warnings; Gradebook score is null.
Lost/invalid/mismatched replies, uncertain server/transport outcomes, failed
readback or receipt persistence remain unknown and never automatically replay.
Readback does not reconcile an earlier unknown. D3 concurrency/native side-field/
notification acceptance and D6 backend/retention/legacy drain/import remain open.

## Focused native retirement

Removed save/release mappings and their sole coordinator
`McpGradeMutationService`; direct source bytes are privately preserved. Mutation-only
test methods/fixture emitters were removed from the shared native service suite;
context/permission/roster tests remain. Frozen fixtures were not regenerated.
Two exact obsolete generated class leaves were individually copied, hashed in
`retired-generated.json` and removed. No blanket clean was used.

`McpAssignmentGradingController` now injects only query service and maps only
`grading-context`. Its wiring test asserts that mapping and retired-class absence.
T09 retains native metadata/evidence/projection/store helpers. Four now-unused
mutation-only methods (`McpGradebookProjection.writeTarget/target`,
`McpGradingEvidence.revision/current`) are recorded in the native ledger for focused
D7 helper/constructor review. Other domain/version/lock/storage callers, the unused
`addDraftAssignment` factory/API, schema, native private records and cleanup remain
preserved pending separate review. No record/data/schema deletion.

## Fresh local verification

- Locked dependency sync passed; `./scripts/check-mcp.sh`: **565 Python tests**, Ruff
  lint/format over **130 files**, mypy over **73 source files**. Frozen public
  schemas/catalogs/descriptions/evaluator/report checks pass unchanged.
- Actual default public SDK/JWT/OBO synthetic HTTP chain covers HTTP observation →
  prepare → save → external receipt read → prepare release → release, student
  denial, setup/announcement compatibility and no custom grading-save/release call.
  Focused facade tests cover permission/identity/unsupported/stale/max-size cases,
  exact private-field/override preservation, no academic validate POST, one send,
  malformed/lost/503 replies and post-readback mismatch with unknown/no replay.
- Explicit Java 17 focused reactor: **38 tests in eight suites**, zero
  failures/errors/skips. Native context/wiring, selected POST credential guard,
  JWT/response/RequestFilter/Sites/Portal and ordinary Login checks pass. Test count
  decreased after retiring ten mutation-coordinator cases and adding one auth case;
  Python facade tests now cover the replacement behavior.
- Python wheel/sdist and Java package builds passed. Wheel bytes match every
  current Python source and exclude editor files. WAR changed class bytes match
  built classes, sole controller mapping is context, and **all 12 retired business
  controller/service classes are absent**. No artifact was deployed.
- Repository guidance, whitespace, required `check_scope.py --verify-progress`,
  full chained private hashes/source overlay, four editor fingerprints, empty
  index and independent custom worktree preservation checks passed.

Logs: `/tmp/sakai-grading-write-python-final.log`,
`/tmp/sakai-grading-write-java-final.log`, `/tmp/sakai-grading-write-package.log`,
`/tmp/sakai-grading-write-wheel.log` (local diagnostics, not live evidence).

Next gates: T09 truthful strict-context representability; T20 complete eligible
roster/content and scoped attachment evidence without changing evaluator identity;
D3/D6/D8 native-role/field/concurrency/durable backend/legacy/live acceptance; focused
D7 helper/domain retirement with record preservation. Release remains additive
compatible auth → accepted matching Python cutover → separately authorized native
retirement, with compatible-native-first rollback. This native tip cannot serve
older Python clients needing retired routes. No deployment, activation, runtime,
Azure, notification or academic operation occurred.
