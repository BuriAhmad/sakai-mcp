# External captures and selected grades — 19 October 2026

Local work only, migration branch `codex/replace-custom-sakai-api`, base/unchanged
HEAD `0f9f44a76f34777b52f56ae03634ffd3a0b3bc6c`. Freshly verified the independent
custom worktree/branch and `main`/`origin/main` at `208d69ac`; support, archived
restructuring and migration commits match the Git handoff. The custom worktree was
only inspected and remains untouched. The original four editor files remain
untracked. No commit, push, branch/worktree reorganization, deployment, activation,
academic operation, Azure change, schema or stored-record cleanup occurred.

## Actual callers and next-five selection

Five further **default implementations** changed, bringing local replacements to
13 of 22. This is not five fully restored workflows or deployed acceptance.

| Tool | Default caller and implementation | Replacement scope |
| --- | --- | --- |
| T12 `export_assignment_submissions` | `mcp/tools.py` → `GradingOperations.export_assignment_submissions` → `workflows/captures.py:Captures.export` | Existing delegated course/native individual grading view/item DTO observations → immutable external inline artifacts and partial receipt. |
| T13 `get_assignment_submission_export` | public tool → `GradingOperations.get_assignment_submission_export` → `Captures.page/manifest` | External owner-bound frozen receipt plus fresh existing native source authorization; no capture/resume on read. |
| T16 `get_assignment_grades` | public tool → `GradingOperations.get_assignment_grades` → `workflows/selected_grades.py` → shared `SubmissionReads.observed_source` | Selected Assignment scores, feedback digest and known flags; release comes from an exact native list cell, separately from returned. Independent Gradebook projection remains unavailable. |
| T21 `get_assignment_grading_proposal` | public tool → `GradingWorkflow.get_proposal` → `GradingOperations.get_proposal` → `Captures.proposal` | Frozen external record plus export lifetime and fresh source identity/authority; no evaluator call or expiry extension. |
| T22 `read_assignment_grading_resource` | public fallback and SDK `resources/read` → same `workflows/resources.py` → original grading facade | Current inline evidence, external captures/manifests and frozen reports; current attachment resources explicitly unsupported. No legacy route fallback. |

The initially investigated fifth candidate was T20 MCQ preparation. Its caller
uses the export manifest, strict grading context, complete roster, frozen evaluator
and proposal persistence. Today's native observations cannot establish complete
expected/hidden/inactive/orphan enrollment or complete attachment evidence. The
unchanged evaluator requires complete authoritative state. An earlier incomplete
manifest check now fails before the residual legacy context path; proposal storage
is external, but T20 **is not counted as migrated**. It still needs its own context,
roster and grading acceptance. No fake completeness, review-only substitute for
marks, or evaluator change was introduced to claim five. T16 was continued as an
independent read instead.

## Existing interfaces and limitations

Source research follows canonical A0/A4/A5/A9, B7/B8/B10 and T12/T13/T16/T20–22.
The new workflows reuse actual default `SubmissionReads`, not another client
behind a flag. Existing `/direct/user/current.json`, course/site/effective-permission
and Site pages reads establish the actor/course/placement. Existing Portal native
Assignment grading navigation positively establishes individual identities before
selected `/direct/assignment/item/{assignment}.json` hydration. Site-wide
`asn.grade` is mandatory; group-only, anonymous, group and peer modes stay blocked.
Native handlers/permissions remain unchanged. Read observations may omit records;
none is promoted to a complete roster or native transaction.

T12 preflights distinct selected submission IDs, exact assignment/site/user
relationships and T19-compatible `http1-` metadata/content observations. It checks
all selected rows before storing intent. A configured durable store is mandatory
before HTTP; the production client uses the existing managed-identity Blob adapter
and has no memory fallback. Tests inject the conditional memory adapter only.
D6 deployment, durability, access, backups, owner import and retention are open.

The owner binds tenant/object/native UID/course/assignment; knowing a UUID is not
a grant. Conditional creation freezes request hash, original expiry (24 hours),
source selections and a private creator nonce. Only the creator captures; a second
worker returns the historical pending/final receipt. The creator uses an ETag to
finalize. A reused UUID with another payload conflicts. Crash/cancel/storage or
permission failure after intent can leave **pending**, with private orphan bytes;
there is no automatic resume, recapture, cleanup or expiry reset. Reads do not
repair pending records. The pending manifest retains all original selections for
reauthorization. This coordinates cooperating MCP workers only, never Sakai rows.

Only exact UTF-8 inline HTML bytes are currently captured, at most 65,535 bytes
per row, 100 selections/artifacts, two capture preparations concurrently. The
maximum new inline capture is therefore 6,553,500 bytes, below the existing
100 MiB overall capture budget. Attachment bytes/ZIP are not guessed or fetched.
Every new row is incomplete, every finalized export **partial**, and completeness
false even when its inline bytes are present. Attachments add an explicit reason.
Metadata/content is observed again after capture; exposed changes produce
`source_changed`. Invisible changes/ABA and missing native fields remain unknown.
Recorded hashes establish stored-byte integrity, not a native causal snapshot.

T13 and R03/R04 load bounded immutable manifests, verify receipt/request/expiry and
artifact identity relations/digests, and reauthorize every selected source user
through fresh native reads. Current source bytes may differ from the frozen
capture; source deletion, omitted identity, permission revocation or changed
submitter denies access. Owner match alone is insufficient. Artifact reads compare
actual length and SHA-256. Public links stay `sakai://`; legacy typed path fields
are internal descriptors and never HTTP destinations. Pending receipts can be read
by T13 but are not a usable resource/evaluator manifest. Cursors bind the stored
manifest; legacy numeric cursors conflict.

T16 source proof: `chef_assignments_instructor_list_submissions.vm:635` renders a
`headers="gradereleased"` cell with `si-check` iff `getGradeReleased()`; it is
separate from returned. `AssignmentReferenceReckoner` supplies
`/assignment/s/{site}/{assignment}/{submission}`. Python requires one native photo,
one exact same-placement grading link with that reference and the correct
Assignment reference, and the recognized release cell. Blank/unknown/missing or
duplicate controls fail. Missing-user rows never supply submission flags. A second
fresh native view checks the selected release observations again; a visible race
conflicts. Modern grader preferences are unchanged; this is the existing list,
not an assumption about a hidden legacy detail form.

T16 returns actual point-display strings (blank stays null, zero remains zero)
and exact emitted feedback hash. It rejects nonpoint/localized scores. Its grade
revision includes the observed release indicator; it is not an ORM version/CAS.
Only submitted individual targets present in the current native grading-list page
are supported; list paging for selected targets is not yet implemented. Independent
Gradebook score/comment/link state and returned-at are not established: nullable
fields stay null, link mode unknown, `gradebook_state=unavailable`, completeness
false. No Assignment score is reused as a Gradebook value. B6 packed/table/selected
summary authorization, identity, precision and comment coverage remain concrete
gates. Separate UI/API reads are not atomic even after matching release indicators.

T21/R05 read frozen external proposals, retaining the frozen numeric proposal
cursor input grammar (export cursors are opaque), and check record/request/config identity,
source-export expiry and current source authority, and reuse unchanged canonical
JSON/CSV report renderers. They do not generate a new proposal from today's
incomplete captures. Tests seed synthetic external records to exercise reads;
there is **no live legacy import or automatic owner conversion**. Raw native
records/old UUIDs are preserved but not magically accessible in the new namespace.
Missing records return not found. Authorized offline mapping/import or a reviewed
drain with retained receipts is required before any release. Original expiry must
survive translation; operation receipts remain owned by the retained native path.

T22 now has no custom-route dependency. R01 remains current-inline-only; **R02
current Assignment files now explicitly return unsupported**, replacing the last
legacy file call. R03/R04/R05 use the external pipeline locally, but full family
parity, attachment support, imported legacy continuity and live acceptance remain
open. Strict resource shapes/report names are checked before remote work. No
resource read performs an academic write or starts/resumes capture.

## Focused native retirement and preservation

Seven more routes retired: Assignment file; export create/read/artifact; proposal
create/read; selected grade query. **16 of 23 historical routes are retired
locally; seven remain.** Removed three now-unreferenced native services:
`McpGradingFileService`, `McpGradingExportService`, `McpGradingProposalService`;
removed their controller dependencies/mappings and sole selected-grades query
method. The query service, authorization, evidence, Gradebook projection, mutation,
store/JSON/auth helpers remain for actual context/save/return/operation callers.
No domain/helper/model/ORM/schema or ordinary UI change was made.

Native tests of retired services were moved into default Python source/store
contracts; retained context/mutation/authorization tests remain. Negative actual
Spring mapping/class-load assertions cover retirement. Original tests/source are
recoverable in the reviewed private checkpoint. Only specifically named retired
generated `.class` files were removed before fresh compilation; no user content or
other worktree was cleaned.

New owner-only read-back-verified checkpoint:
`/Users/burhanahmadkhan/Downloads/Sakai-External-Capture-2026-10-19/` (249 initial
source/evidence files, tar and SHA manifest, plus explicit retired-source copies).
`continuation-2026-10-19.json` records exact before/after path hashes against
`0f9f44a7`, checkpoint hashes and decisions. `check_scope.py --verify-progress`
validates that continuation in addition to the original start comparison and Git
organization ancestry. **baseline.json, implementation-start.json,
git-organization.json and original/private historical checkpoints are unchanged.**
No old manifest is rewritten to pretend new implementation was present at start.

## Fresh verification and release gate

Fresh command results, package hashes and exact totals are recorded in
`progress.json` after verification. Logs:
`/tmp/sakai-external-capture-python.log`, `/tmp/sakai-external-capture-java.log`,
`/tmp/sakai-external-capture-package.log`, `/tmp/sakai-external-capture-wheel.log`.
Default SDK/JWT/OBO covers capture/status/selected grades/resource fallback;
source-derived facade tests cover owner/permission/identity/record and byte errors,
concurrent creators, pending restart, expiry without deletion, changed sources and
explicit MCQ refusal. Frozen public catalogs/models/evaluator/report fingerprints
are unchanged. Source-derived HTML is not exercised native rendering evidence.

Next concrete local gate: B7 complete eligible roster and B8 attachment ACL/byte
integrity, plus B6 selected independent Gradebook readback and strict context field
coverage. D3 remains required before official grading cutover; D6 before external
store activation/import. For any separately authorized runtime release, preserve
**additive native auth retaining required routes → accepted exact Python HTTP
cutover → native retirement**. This native tip is incompatible with older clients
requiring any retired route; rollback must select a compatible pair. Nothing here
is live or deployed and no runtime action is requested by this local-only task.

Final verification: **451 Python tests**, Ruff lint/format (118 files), mypy
(66 source files); **91 Java tests in 19 suites**, plus **19 final focused tests**
after unused dependency retirement, all pass. Wheel/sdist and final WebAPI package
builds pass. Archive inspection matches the final wheel source and proves retired
classes/mappings absent from the WAR. The first WAR inspection found retired
classes in Maven's generated staging directory; those exact five generated class
entries and the generated WAR were removed and the final package rebuilt/inspected.
No source, user artifacts or other worktree was cleaned.

The retained grading context's Python facade also marks current Assignment
attachments unreadable and clears their resource revision, so its shared presenter
cannot advertise a retired file link. That transitional-context adaptation is not
counted as another migrated tool. Original baseline/start manifests/archive and
the full private Git-organization archive were freshly hash-verified unchanged.
Fresh source scope/preservation and guide/whitespace checks are recorded in progress.
