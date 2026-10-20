# Remaining evidence gates and focused native helper retirement — 20 October 2026

No new actual default replacement is claimed: **20/22 defaults replaced locally,
22/23 historical business routes retired locally**. T09 and T20 remain; no resource
family is fully migrated. Existing grading write functionality and its narrow
single-row/integer/unlinked/plain-text limits are unchanged. No live/deployed
acceptance, feature activation, runtime/Azure change or academic operation.

## Fresh state and preservation

Verified migration branch `codex/replace-custom-sakai-api` and HEAD
`0f9f44a76f34777b52f56ae03634ffd3a0b3bc6c`. Independent custom worktree remains
clean on `codex/sakai-custom-native-api` at
`208d69ac624910a29a7529934ddcc18bbac853e8`; main remains at that baseline. Index is
empty. No branch switch, reset, clean, staging, push or Git reorganization.

Before editing, created and readback-verified owner-private checkpoint
`/Users/burhanahmadkhan/Downloads/Sakai-Evidence-Review-2026-10-20` with 71 manifest
paths and 67 archived source paths. All four editor files were fingerprinted and
excluded from the archive. The new named continuation pins the exact grading-write
predecessor; all original preservation records/manifests/archives remain immutable.
The original private Git-organization manifest and archive hashes were freshly
verified too. No archive was extracted over the checkout.

## T09 strict context: actual caller and representation

The public SDK tool still calls `GradingOperations.get_assignment_grading_context`,
which obtains the retained native query result and presents the frozen strict
`GetAssignmentGradingContextResult` contract. The Python capability hints remain
false for prepare/save/release because this context's native semantic revision is
incompatible with the new HTTP grading observations. Its attachment links remain
unavailable as documented in prior increments.

`GetAssignmentGradingContextResultAssignment` requires non-null native
`scale_factor`, `deleted`, `group_submission`, `anonymous_grading` and
`native_release_grades`, among other fields. The existing Direct DTO emits display
maxima and grade type, not the raw scale factor or native Assignment release flag.
A row's returned/released cell is not the Assignment release flag. Edit-form
observations and English display precision do not recover arbitrary stored scale
or certify every required field. Nullable/warning fields do not make fabricated
required fields valid. Existing metadata remains useful through T19/T16; no
fail-closed-only implementation is counted as a migrated context.

Source: `contracts/grading_native.py`, `sakai/grading.py`, `mcp/tools.py`,
`mcp/presenters.py`, `McpGradingQueryService.context`,
`McpAssessmentService.revision` and `AssignmentEntityProvider.SimpleAssignment`.
The semantic hash remains unchanged and is now called only by the retained query
service in production. This review does not claim every conceivable existing
interface has been exhausted; it records the current source-backed gap.

## T20 complete-input gate and additional roster candidates

Public `prepare_assignment_mcq_grades` calls `GradingWorkflow.prepare_mcq`.
It first reconciles an existing owner-bound immutable proposal, then reads and
authorizes the export manifest. Current exports remain partial. The complete-input
gate rejects them before native context, evaluator invocation or proposal
persistence. Existing frozen-proposal reads were already implemented; returning one
is not a new migration completion. The evaluator source/fingerprint, reports,
canonical config and complete-input checks are unchanged.

Additional source review:

| Existing interface | Observed behavior | Remaining acceptance gate |
| --- | --- | --- |
| Native instructor submission list | Stored submission rows carry stable user IDs; the no-submission branch emits sort name and status only. Its checkbox/user-photo identifiers exist only in the stored-submission branch. | Never match missing students by display name; exhausting pages does not establish their identities. |
| Direct `assignment/gradable` | Computes `allowAddSubmissionUsers` and visible users internally, then filters/maps stored Assignment submissions. `totalSubmissions` is the resulting submission-map count. It does not return the internally computed user inventory. | Cannot infer the missing-student roster from the internally available list or from total submissions. No route was adopted. |
| Direct site memberships / membership provider | Location-scoped membership can provide native IDs, active status and roles, with independent roster/group access checks. It filters invalid/orphaned users through user-directory resolution and applies privacy/sanitization according to authority. | Grade authority alone is not roster authority. Source omissions and pagination must be characterized; do not infer complete eligibility from visible members. |
| Direct site role permissions (`site/{id}/perms`) | Returns role/function metadata only to native admin/site maintainers. Does not list per-Assignment eligible users. | No role-name guess or permission bypass. A role's local functions are not automatically equivalent to Assignment-reference realm unlock eligibility. |

Exact source locators:

- `chef_assignments_instructor_list_submissions.vm`: `$submission` and no-submission
  branches; no-submission emits `$!siteUser.sortName` only for student identity.
- `AssignmentEntityProvider.getGradableForSite`: `allowAddSubmissionUsers`,
  `getSelectedGroupUsers`, stored submission iteration and response `totalSubmissions`.
- `SiteEntityProvider.redirectMemberships`, `handlePerms` and
  `MembershipEntityProvider.getEntities`, `getMembers`, `isAllowedAccessMembers`.
- `EntityMember`: stable `userId`, `memberRole`, `active` and optional resolved
  directory fields, distinct from eligibility proof.
- `AssignmentServiceImpl.allowAddSubmissionUsers`: delegates to
  `securityService.unlockUsers` on the Assignment reference.
- `SakaiSecurity.unlockUsers`: resolves reference authorization groups, gets users
  allowed in those realms, resolves directory users and excludes role-view users.
- Retained native `McpGradingQueryService.roster`: additionally filters active site
  membership, submission/grade role functions and current scoped evidence; it also
  accounts for orphan/duplicate records. Generic membership is not this calculation.

A concrete pagination issue is visible in the current membership provider's
`getEntities` source: when `count < search.getStart()`, the loop continues before
incrementing `count`; positive start does not advance normally. Its positive limit
condition uses `count > limit`. This is a **source finding**, not rendered/delegated
acceptance or authorization to fix the native provider. Do not use conventional
pagination exhaustion to certify completeness. A separately verified bounded
single-response strategy or another existing roster path remains research work.
No membership/role credential reach was added in auth and no candidate was wired
as a fallback. Complete captured attachment/MIME/byte evidence remains B8.

## Focused native retirement and retained callers

After repository-wide Java main/test caller review, removed only:

- `McpGradebookProjection.writeTarget` and `target`.
- `McpGradingEvidence.revision` and `current`.

Their sole former production coordinator was retired in the grading-write
increment. They had no remaining test callers. Removed six now-unused constructor
collaborators: AssignmentService/SiteService/GradingAuthz/evidence from projection,
and metadata/authorization from evidence. Removed unused mutation-era test mocks.
The two containing classes remain because current context still calls their
mapping/link/capability methods. No source class was deleted in this increment.

`McpGradebookProjection.linked`, `link`, `writable` and its grading/authorization
collaborators remain. `McpGradingEvidence` retains identity, attachment/content,
revision/flag/override and entry mapping with Assignment/content/user services.
Native query still owns semantic Assignment revision, ordinary authorization,
scoped roster and configured-store capability checks. No permission check was
removed from an active path. Spring's actual component scan wires the reduced
constructors; reflection assertions cover absent methods and retained projection
methods. Source and rebuilt class inspection confirm the removals.

This closes only the four-method cleanup deferred in the prior ledger. Remaining
D7 factory/hydration/version/lock/storage and ordinary API compatibility reviews
remain open, as do D6 legacy imports/drain, ownership/retention and cleanup.
`AssignmentService.addDraftAssignment` remains retained for separate API/ordinary
Assignment review. No schema, stored record, export, proposal, receipt, academic
data or cleanup configuration was deleted/changed.

## Fresh local verification

- Locked dependency sync and full `check-mcp.sh` pass: **565 Python tests**, Ruff
  lint/format **130 files**, mypy **73 source files**. Actual default SDK/JWT/OBO
  supported write/receipt flows, MCQ partial-input rejection and frozen public
  contract/catalog/description/evaluator/report checks pass. No Python implementation
  or baseline fixture changed in this increment.
- Explicit `/opt/homebrew/opt/openjdk@17` focused reactor: **38 Java tests in eight
  suites**, zero failures/errors/skips. Retained context/roster/permission cases,
  reduced constructor wiring and method absence, delegated JWT/RequestFilter/Sites/
  Portal and ordinary Login pass. No new native business behavior was added.
- Fresh wheel/sdist and Java package builds pass. Wheel matches all current Python
  source bytes and excludes editors. WAR matches changed helpers and retained
  query/controller class bytes; all 12 previously retired business classes remain
  absent. `javap` verifies reduced constructors and absent four methods.
- Required scope/progress and chained preservation checks, repository guidance,
  whitespace, four editor fingerprints and independent worktree/ref/index checks
  pass. No generated class deletion or blanket clean was needed for method-only
  retirement; recompilation replaced the changed class outputs.

Local logs: `/tmp/sakai-evidence-review-python.log`,
`/tmp/sakai-evidence-review-java.log`, `/tmp/sakai-evidence-review-package.log`,
`/tmp/sakai-evidence-review-wheel.log`. No artifact was deployed.

Next concrete implementation gate is an existing complete eligible-roster/content
path with stable identities and explicit authority/omission behavior; a generic
membership list cannot yet supply that guarantee. T09 separately needs truthful
required native context fields within the frozen public contract. Keep researching
independent gaps without changing the evaluator, inventing complete state or
replaying uncertain writes. D3/D6/D8 actual native-role/concurrency/backend/legacy/
release compatibility acceptance remains outstanding. Release ordering and older
client incompatibility remain as documented in the grading-write evidence.
