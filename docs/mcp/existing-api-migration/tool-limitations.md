# Known tool limitations

Reviewed against the local implementation on **21 October 2026**, branch
`codex/tool-migration-development`. This is the current limitations reference for
maintainers and tool consumers. The [canonical plan](implementation-plan.md)
governs implementation; [coverage](coverage.json) and [progress](progress.json)
record migration state. Update this reference whenever a limit is discovered,
changed or resolved, and link the implementation and verification evidence.

**Current local proof refresh:**21 current facades use existing HTTP/external records; server MCQ preparation is intentionally retired and legacy proposal/report reads remain. Fresh normal regression **585 passed**, focused native **31 tests/13 suites passed**. The catalog regression gate is closed; delegated context/roles, attachment/source/integrity/isolation and intended CLI file delivery remain unaccepted. Separate attachment readiness and Skill validation errored before executing checks (`tests` and `yaml` imports respectively), without repair. See [current results/proposed corrections](proof-refresh-2026-10-21.md). Native retirement stays22/23; broader resource and write limits remain.

## How to interpret results

- `coverage.complete=false` or `completeness.complete=false` means the result must
  not be treated as an exhaustive inventory, complete roster or proof of absence.
  An empty result can reflect native visibility, skipped serialization or filtering.
- `source_limit_reached` concerns a public output cap; its absence does not prove
  that upstream data was complete. Public pagination does not bypass source caps.
- Null/unknown flags, timestamps, history and overrides are unknown evidence, not
  false, zero or an absence of restrictions.
- `http1-` revisions and cursors describe observed fields. They are not native
  database versions, locks, atomic snapshots or compare-and-swap guarantees.
  Repeated reads can see concurrent changes; grading writes need their own accepted
  preconditions and concurrency policy.
- Permission/identity failures remain explicit. Unsupported or ambiguous sources
  do not fall back to retired business routes or a broader privileged identity.

## Limits by replaced tool

### `list_my_courses` — T01

**Current restrictions:** Returns the first **500** visitable course sites in
native-compatible title/ID order. It is not an unlimited site inventory and has no
public continuation beyond that cap. Rich membership/site fields are discarded.
Public, unpublished or soft-deleted site state can be masked by the existing DTO;
Python uses exact identity and additional visit/status evidence. Ambiguous masked
states without enough evidence fail rather than guessing visibility.

**Practical effect:** A course missing from the capped result is not proof that it
does not exist or that membership has been removed. Site discovery and per-course
access checks occur separately, so concurrent changes can affect the observation.
Native membership caches, SQL behavior and large-inventory performance have not
passed live acceptance.

**Source/evidence:** [course facade](../../../services/mcp/src/sakai_mcp/sakai/courses.py),
[access checks](../../../services/mcp/src/sakai_mcp/workflows/access.py),
[T01 characterization](t01-course-cutover-2026-10-19.md).

### `get_my_grades` — T02

**Current restrictions:** Requires `gradebook.viewOwnGrades` and a resolvable native
Gradebook placement. Uses the current-user StudentPage, with exact released
item title/ID correlation. Duplicate titles or IDs, conflicting score/maximum
observations and unsupported formatting can fail. Grader/mixed roles never use
aggregate grades as their own score; their supported metadata route may initialize
native Gradebook state and is attempted once.

UI scores may have **display precision**, rather than full stored precision.
Maximum parsing accepts the native `/ <decimal>` format; locale grouping/comma
formats are unsupported. Percentage/letter displays are not guaranteed to
correlate with numeric API values. Maxima may remain null where no trustworthy
source exposes them. The native own-view parser supports at most **500 displayed
rows**; grader metadata is bounded at **5000 items**, within the transport budget.
Only rows exposed by the accepted own view are returned, without an all-item
completeness guarantee.

**Practical effect:** Do not use this result as exact raw grading evidence or
substitute aggregate averages. The public `coverage` advertises that display
precision may apply. HTML and metadata are separate reads, not an atomic snapshot.
Actual StudentPage rendering, locale combinations and mixed-role behavior remain
live acceptance gates.

**Source/evidence:** [own-grade workflow](../../../services/mcp/src/sakai_mcp/workflows/own_grades.py),
[UI parser](../../../services/mcp/src/sakai_mcp/contracts/gradebook_ui.py),
[five-tool evidence](five-tool-cutover-2026-10-19.md).

### `get_course_announcements` — T03

**Current restrictions:** Main-course/main-channel messages only, with a **3650-day
posting window**, at most **1000 upstream provider rows** and **50 public rows**.
A response reaching the upstream cap is rejected as unsupported. Older messages
and merged-channel-only messages are not a complete archive of visible content.
The native provider can swallow channel/DTO-decoration failures and trim/reorder
before Python selects main-channel messages. A short valid response therefore
cannot certify completeness. The public result always reports
`coverage.complete=false`.

**Practical effect:** Empty/short lists are not proof of no announcements. Every
page reauthorizes; another actor, a changed delivered observation or an old numeric
cursor conflicts. Exhaustive native list/detail enumeration remains open. Actual
role/group/draft/scheduled visibility and configured reorder behavior still require
live acceptance.

**Source/evidence:** [announcement parser](../../../services/mcp/src/sakai_mcp/contracts/announcements.py),
[public coverage and pagination](../../../services/mcp/src/sakai_mcp/mcp/tools.py),
[provider characterization](read-cohort-cutover-2026-10-19.md).

### `get_course_submissions` — T04

**Current restrictions:** Requires **site-wide `asn.grade`**. Group-only TAs are
unsupported. A native grading list must positively establish an individual view
before selected-item hydration; known anonymous/group assignments and views
without positive identity evidence fail before hydration. Peer-assessment data
and draft assignments are unsupported by this read path. Native list discovery
is bounded to **20 pages**; missing/ambiguous controls or repeated pages fail.

Returns **submitted individual rows only**, the first **100** by submitted date
(null last) and ID. Native DTOs may omit failed rows or inactive submitters.
Missing/unsubmitted/orphan roster entries are not established. Dates have **whole
second precision**. Public coverage is explicitly incomplete.

**Practical effect:** This is submitted metadata, not a full class roster or a
safe basis for deciding who failed to submit. Pagination cannot recover records
outside the source/public caps. Cross-course/assignment identity mismatches and
malformed/duplicate records fail. Actual native role/serializer/supplementary-data
entitlement and concurrent mode-change behavior need live acceptance.

**Source/evidence:** [shared submission workflow](../../../services/mcp/src/sakai_mcp/workflows/submissions.py),
[DTO validation](../../../services/mcp/src/sakai_mcp/contracts/submissions.py),
[five-tool evidence](five-tool-cutover-2026-10-19.md).

### `list_assignment_submissions` — T10

Shares T04's permission, individual-mode preflight, serializer, peer-assessment,
whole-second timestamp and native navigation limitations. The grading feature must
be enabled separately. The selected Assignment DTO is bounded at **5000 source
rows** and by the HTTP response budget; this is not unlimited remote pagination.
Local pages describe a newly fetched observation on every invocation, bound to
actor/site/assignment. Changed observations or legacy cursors conflict.

**Current evidence gaps:** No verified complete expected roster; missing,
unsubmitted and orphan rows are not enumerated. Raw release/lock flags,
attempt/history completeness, overrides, return timestamps and attachment bytes
are unavailable or unknown. Do not interpret native `returned` as grade release.
Displayed point grades are not scaled again; unrecognized localized/letter formats
fail explicitly. The result has `completeness.complete=false`.

**Practical effect:** Automated grading/proposal preparation continues to refuse
this incomplete evidence. A successful page read does not imply readiness to mark
or release grades, even if every returned row appears valid.

**Source/evidence:** [submission workflow and paging](../../../services/mcp/src/sakai_mcp/workflows/submissions.py),
[entry mapping and warnings](../../../services/mcp/src/sakai_mcp/contracts/submissions.py),
[five-tool evidence](five-tool-cutover-2026-10-19.md).

### `get_assignment_submission` — T11

Shares T10's scope and field limitations, including its grading feature gate.
Reads the selected assignment's bounded submitted observations to locate one row;
it is not an unrestricted single-submission lookup. A row omitted by the native
serializer yields unsupported, rather than a fabricated missing-record conclusion.
Private notes are not exposed. Inline text and feedback are current observations,
not submission history or immutable captures.

The public presenter exposes inline content through a resource. Inline retrieval
reauthorizes/refetches and checks the observation revision, then returns exact
UTF-8 bytes/hash, bounded at **65,535 bytes**. DTO inline/comment fields also have
character bounds. Submission **attachment downloads are unsupported**: descriptors
have `readable=false` and no fabricated resource revision. A hash of observed
inline text or attachment metadata does not establish attachment-byte integrity.

**Practical effect:** Text-based inspection is locally implemented; attachment-based
grading and complete evidence capture are not restored. Do not treat missing links
or unknown flags as evidence that a student supplied no file or has no release.

**Source/evidence:** [submission DTO and mapping](../../../services/mcp/src/sakai_mcp/contracts/submissions.py),
[inline read](../../../services/mcp/src/sakai_mcp/workflows/submissions.py),
[resource dispatch](../../../services/mcp/src/sakai_mcp/sakai/grading.py),
[five-tool evidence](five-tool-cutover-2026-10-19.md).

### `create_course_announcement` — T05

**Current restrictions:** Nonblank plain title/body, at most **200 title
characters** and **10,000 body characters**. Publishes immediately to the site's
main channel through native Add/form controls with **optional notification**
priority. The public tool does not support selecting role/group recipients,
scheduling, attachments, highlight options or a caller-selected author. Rich HTML
arguments are escaped as plain text.

A configured durable private journal is required **before any HTTP request**.
Without it the tool returns `DEPENDENCY_UNAVAILABLE`. There is no production
memory fallback. Store provisioning, retention/ownership/access/backup acceptance
(D6), actual native form rendering and notification delivery remain unresolved
acceptance/configuration gates; local construction does not provision or activate
anything. See [store configuration](../../../services/mcp/README.md#existing-announcement-creation-journal).

**Uncertain writes:** Intent/Sending persist before one POST. Timeout, error,
unrecognized response or ambiguous readback yields `AMBIGUOUS_WRITE_OUTCOME` and
is never automatically resent. The operation might already have created the
message. A **new invocation is a new intent**, not a safe retry; there is no public
idempotency key. Reconcile the native message and journal before considering a
fresh creation. The current public interface has no dedicated journal-recovery
tool.

A new native list reference plus matching title/body/time readback establishes an
observed match, **not a causal receipt**; the result explicitly reports
`causation_guaranteed=false`. Concurrent identical creations, native normalization,
provider omission/truncation or clock differences can remain ambiguous. Optional
notification priority does not prove email delivery.

**Source/evidence:** [creation workflow](../../../services/mcp/src/sakai_mcp/workflows/announcements.py),
[single-send journal](../../../services/mcp/src/sakai_mcp/workflows/operation_journal.py),
[five-tool evidence](five-tool-cutover-2026-10-19.md).

### `list_assignments` — T19

**Current restrictions:** Grading feature gate and **site-wide `asn.grade`** are
required. Group-only TAs fail before the hydrated site API. The existing API
hydrates submissions/supplementary content; Python discards these fields before
public output/hashing, but this is still a bounded site-wide backend read. It must
not be reused as metadata-only setup planning or a group-scoped discovery shortcut.

Bounded at **5000 assignments** and the response budget, excludes drafts, and
validates exact site/IDs. Serializer omissions, deleted/historical entries and
unexposed configuration are not a complete inventory. `http1-` metadata/page
revisions cannot substitute for native configuration revisions or grading/setup
write preconditions.

**Practical effect:** Current discovery supports site-wide graders with disclosed
source limits. Native metadata-only discovery for scoped TAs, cold serializer and
supplementary-content entitlements, full configuration coverage and live role
acceptance remain open.

**Source/evidence:** [discovery facade](../../../services/mcp/src/sakai_mcp/sakai/grading.py),
[assignment parser](../../../services/mcp/src/sakai_mcp/contracts/assignments.py),
[read/discovery evidence](read-cohort-cutover-2026-10-19.md).

## Practical setup defaults — T06/T07/T08, 20 October 2026

These actual defaults now use existing Assignment list/edit/save/post HTTP and
external journals. They are locally replaced with **partial functionality**, not
full parity or live acceptance. Public schemas/catalog descriptions remain frozen;
unsupported combinations fail explicitly and returned completeness/partial fields
carry the narrower behavior. [Source and tests](setup-cutover-2026-10-20.md).

### `get_course_assessment_context` — T06

Requires site-wide `asn.new`, `asn.revise` and `gradebook.editAssignments` plus a
resolvable Assignment placement. Group-only edit/grading permissions do not suffice.
Reads the existing native list and edit forms without hydrating Direct submission
DTOs. Enumeration is bounded to **20 pages / 500 editable rows**; native group/search/
draft-owner preferences can narrow it. Only the first **20** editable rows receive
form-revision observations. Effective actor UID/EID/site/timezone are bound to the
native Portal header; the timezone is the acting user's effective native zone,
**not a verified course policy**. Its preference-versus-server source stays unknown.

The frozen full Assignment shape requires unexposed deletion/release/integration
fields. It is **not filled with guessed flags**: `assignments=[]` has explicit
`sections.assignments.status=unavailable`. Available ID/title/draft/form-revision
observations are labelled `assignment_metadata_only: <JSON>` warning entries;
null revisions mean no usable edit revision was established. Category selector
IDs/names are similarly labelled `gradebook_category_choice_metadata_only`.
These entries support planning and obtaining the observation revision for publish;
they are not complete Assignment/Category records or absence claims. This is an
interim representation within the unchanged strict contract, not full metadata parity.

Reads the **existing metadata-only** `/api/sites/{site}/grading/item-data` endpoint,
already used by the client, after native course and item-edit authority checks.
The native service permits assignment metadata to editors or graders. Setup never
requests student grades, submission bodies or the instructor score table, including
during link verification. Response budget is **1 MB**, with at most **500 items and
500 categories**. Item context must exactly match the site; IDs and duplicate checks
are strict. Native item flags, external references, maxima and exposed category
weight/drop/keep/equal-weight/extra-credit rules are returned. Nullable or omitted
required flags/rules do not become false/zero: the affected full object is omitted
with an explicit ID-labelled warning. Complete=false and permission-scoped status
remain; missing objects do not prove absence.

Maxima/weights use native double precision. Item due dates, full Gradebook mode/entry/
display settings and group Gradebooks remain unavailable. The metadata read may
initialize native Gradebook backing state; it has no automatic retries. Native DTO
serialization failures and real editor/role behavior remain acceptance gates.
Calendar is not read: section unavailable, events empty, no absence claim. Explicit
valid calendar windows are preserved; the old default UTC window (-14 days through
+42 days from today's midnight) remains. Capabilities reflect observed native
permissions and do not guarantee every adapter operation is implemented.

### `create_assignment` — T07

Useful local subset: **individual/site-wide points assignments**, the five existing
public submission modes, draft or posted publication, finite dates and structured
resubmissions (**0–10 or unlimited -1**; non-electronic supports 0). **100 UTF-16 code-unit
native title limit**, a conservative **65,535 UTF-8 byte instruction limit**,
**11-character points field**, native **minute precision** and
date-picker upper year **2099** apply; finer instants are rejected, never truncated.
Requested instants are converted to the observed native acting-user timezone without
changing preferences; unrecognized native timezone aliases and ambiguous/nonexistent
DST wall times fail. Writes currently
require an English numeric locale; other locales fail before POST rather than risk
native decimal interpretation. Native scale/rounding remains a readback/acceptance
limit: requested displayed points must match readback numerically.

Current Assignment attachments, group/group-Gradebook/anonymous/peer/review/rubric
variants and linked calendar deadlines are unsupported before mutation. New-form
optional auto-announcement/calendar defaults are explicitly unchecked for the
requested `none` policy; forced controls fail. Native unrequested form defaults can
still affect other ordinary policies, so full configuration is not certified.

Gradebook mode `none` and native `new_external` are supported. External creation
requires native Gradebook item-edit authority, passes native metadata authorization
before mutation, and requires **released=true,
counted=true**, matching the existing native create behavior; other policies fail
before write, avoiding an unwanted transient release. A configured category must
be selected by its rendered existing ID. When native category choices are rendered, requesting
uncategorized plus counted=true is rejected because the native table treats that
item as uncounted. No category, weight, existing item or grading policy is edited.
An exact metadata-only external Assignment reference/app/item/category/flag readback
establishes only the observed stored link flags, not effective course-grade calculation,
full settings/precision or an atomic setup transaction. Empty/hidden category settings
can remain unknown. A visible duplicate Gradebook title conflicts before creating a
new external item; no title is used as the authority for link identity.

A configured durable private journal is mandatory **before HTTP**. Prepared/Sending
persist before **one academic POST**. Response loss, 5xx, unknown controls, ambiguous
new-ID delta, scope/binding or core readback mismatch never cause automatic resend.
A new invocation is a new intent; native title checks and visible-ID deltas do not
establish cross-request idempotency or discover hidden drafts. Native first persistence
is not the old custom private-first factory, and post/link stages are not atomic.

After a unique visible new ID, required fields and draft/posted state are observed,
results deliberately remain **`outcome=partial`, `assignment=null`,
`remaining_steps=[verify_setup]`, `retry_safe=false`** because the strict full object
cannot be verified. The saved ID, timestamp, operation ID and `configuration_revision`
warning are preserved. Instruction normalization differences additionally require
`verify_assignment`; they are explicitly reported rather than treated as equal.
A later transient/unsupported Gradebook read produces an unknown link with the
known Assignment ID. Identity/permission failures remain errors, with previously
observed IDs retained privately. Matching source state is not a causal receipt.
Do **not** repeat create merely because verification is partial or unknown.

### `publish_assignment` — T08

Publishes one **currently visible/editable draft** through its rendered edit form.
Get the form observation revision from context metadata or a prior create result;
old custom configuration tokens and T19's different metadata hashes are not equivalent.
Changed observations conflict before POST; an already posted assignment conflicts
instead of being reposted to resume links. Inactive visible/resubmission date defaults
are excluded from the revision so native default-time changes do not invalidate an
otherwise unchanged draft. Active fields and preserved controls remain guarded by
an observation only; concurrent UI changes/ABA can occur between read and POST.

Preserves existing form fields and uses the same locale, individual/points, attachment,
feature and integration restrictions as creation. Existing checked calendar/auto-
announcement state is rejected, rather than silently deleting/regenerating links or
sending notifications. JavaScript-synchronized tag controls and raw rubric controls
are also rejected during publish: forwarding an empty raw tag input can clear existing
associations. The existing native rubric handler skips association updates when no
rubric parameters are posted; explicitly detected active rubrics remain unsupported. No bulk publish, edit API, repair/resume, native CAS or automatic
retry is provided. Uses the same durable one-send journal and explicit partial readback
result. A caller must inspect partial/unknown results before any further academic action.

**Resolution gates:** actual native rendered/delegated role and timezone acceptance;
full Assignment/Category/Calendar fields; scoped attachments; additional Gradebook
flag edits and verified partial recovery; durable retention/ownership and compatible
release ordering. These do not block useful local tests of the supported subset.

## Shared transport, resource and release limits

Existing JSON responses default to a **1,000,000-byte** budget. Native HTML is also
bounded; unrecognized markup or missing/ambiguous placements and controls fail.
These bounds may reject larger legitimate courses/assignments before row caps are
reached. Browser navigation interprets only accepted rendered URLs/controls;
source-derived synthetic fixtures do not prove every customization or Wicket/form
variant. No arbitrary JavaScript or unknown native workflow is executed.

All five resource families retain functionality/legacy/live acceptance gaps. R01
supports current inline bytes only. R02 current Assignment attachments explicitly
returns `UNSUPPORTED_CAPABILITY`; it no longer calls a custom native file route.
The retained context facade marks these attachments unreadable with no resource
revision, so its presenter does not advertise unusable links.
R03/R04 captured bytes/manifests and R05 frozen reports now use external records
with fresh native source reauthorization. Legacy records require a separately
reviewed offline owner mapping/import; their bytes/UUIDs/expiry remain preserved,
but are not automatically accessible in the new namespace.

Two tools still require migration: `get_assignment_grading_context` (T09) and
`prepare_assignment_mcq_grades` (T20). The native context's strict full Assignment
and semantic configuration hash remain unavailable through researched existing
reads. Its prepare/save/release capability hints are now false: obtain HTTP
metadata/row observations through T19/T11 or T16 for the supported write subset.
No unavailable fields are guessed. MCQ still requires complete roster/content
and attachment evidence; it is not counted as migrated.

The local native tip has retired **twenty-two** historical routes; one remains.
It cannot serve older Python clients needing retired routes. Preserve compatible
additive-auth native revision → accepted Python HTTP cutover → native retirement,
with compatible-native-first rollback. Nothing is newly live or deployed.

## Additional locally replaced defaults

### `export_assignment_submissions` — T12

Requires the grading gate, configured durable external store and the same fresh
site-wide, submitted-individual source authority as T10/T11. Without store
configuration it fails before HTTP. Group-only/anonymous/group/peer modes remain
unsupported. Exact selected assignment/content observations must match before
conditional intent creation. At most **100 distinct selections**, **100 inline
artifacts**, **65,535 UTF-8 bytes per inline artifact** and **two preparations**
concurrently; new inline captures cannot exceed 6,553,500 bytes. Attachments and
ZIP are unsupported. No content is rendered, normalized or extracted.

Every new finalized export is **partial**, every row incomplete (or source_changed),
and completeness false. Exact captured inline bytes/hash remain useful for manual
inspection; they cannot establish a complete roster/evidence set for MCQ scoring.
Exposed source changes after capture are recorded; unexposed changes/ABA are not
covered. This is not a native snapshot or a lock against UI/student writers.

An export UUID freezes the owner, payload hash and original **24-hour expiry**.
Same payload returns the existing pending/final outcome; different payload
conflicts. Conditional creator/ETag handling prevents cooperating workers from
recapturing the same intent. An interrupted capture may remain **pending** with
private unreferenced bytes. Neither a duplicate invocation nor a read resumes,
cleans or extends it. Permission/storage errors after intent require explicit
reconciliation. D6 retention/backup/actual Blob durability and legacy import remain
activation/release gates; no production memory fallback is provided.

### `get_assignment_submission_export` — T13

Reads frozen external receipts, reauthorizing **every selected submission/user**
against current native source access. Tenant/object/native UID/course/Assignment
owner binding and original expiry are enforced. A removed/omitted row, changed
submitter or revoked permission denies access. Newer source bytes do not rewrite
the historical capture. Receipt, request and artifact relationships/digests are
checked; artifact downloads verify actual stored length/hash.

Pending status can be inspected but cannot be used as a completed resource or
evaluator manifest. The read never captures/resumes/repairs. Pages hold at most
100 artifacts and use manifest-bound opaque cursors; old numeric cursors conflict.
Actual external persistence, legacy owner import and delegated role acceptance
are open; a missing external UUID is not proof no native historical record exists.

### `get_assignment_grades` — T16

Requires site-wide `asn.grade`, submitted individual rows and recognized native
list photo/Assignment/submission link/release-cell relationships. Selected reads
follow **rendered Next controls**, at most **20 grading pages** and **5000 identified
submitted rows**, in the same delegated conversation; Assignment discovery is
separately bounded to 20 pages. A disabled Next must terminate enumeration.
Repeated pages, duplicate submission/student identities, ambiguous/missing controls,
foreign links, missing release cells and unknown indicators fail explicitly.
Group-only/anonymous/group/peer variants remain unsupported. The existing `si-check`
indicator establishes release; native `returned` remains separate. Two enumerations
reject an exposed selected release change. They are not a native snapshot or CAS;
search/group preferences can still narrow the native list.

Returns Assignment **display point strings**, blank as null and zero as zero.
Localized/letter/nonpoint scores are unsupported. Feedback hash covers the emitted
comment; returned-at remains unknown. An `http1-` revision describes observed
Assignment/release fields and cannot serve as a native commit precondition.

Independent Gradebook **display scores and link flags** are now read from B6 only
when fresh native permissions include all of `gradebook.gradeAll`,
`gradebook.editAssignments` and `section.role.instructor`. Other authorized Assignment
graders retain Assignment/release reads with explicit unavailable Gradebook fields;
the broader instructor table is never opened for them. Eligible readers use the
configured Gradebook placement's existing `/grades` mount. Site/form Gradebook UID
and `settings.gUid` must equal the requested site; group Gradebooks are unsupported.
The column must have the exact Assignment external reference and native external
application ID, external maintenance and typed release/count flags. User IDs are
exact; names/titles/order are never correlation keys. Absence in this potentially
filtered table does **not** prove 'not linked'. Failed/unsupported eligible reads
fail the operation; no legacy or Assignment-score substitution is used.

B6 is a **bounded full instructor table read**, even though only selected values
are returned. Native preferences may initialize on first visit. Payload is capped
at **1 MB**, the matrix at **100,000 cells**. Category columns participate in matrix
indexing. Points mode only; JSON uses the native double representation, packed
fractions can round to hundredths. The baseline's ambiguous fraction-carry encoding,
negative/excused scores and values outside the fixed public numeric grammar fail.
Raw stored precision and comment bytes are unavailable. Available means selected
display-score evidence, including an observed null; it does not certify exact stored
values, projection equality, complete Gradebook state or comments. Completeness
remains false, with explicit reasons/warnings. Assignment, release and Gradebook
observations are separate and can race, including unobserved ABA changes.

**Evidence/resolution gate:** [20 October readback evidence](readback-2026-10-20.md).
Actual native rendered data/roles, deployment compatibility, display precision and
comment handling require separate acceptance. B6 score-only adoption closes neither
D3 concurrency nor the full grading-context field gate.

### `get_assignment_grading_proposal` — T21

Reads frozen external records only, checking owner/site/Assignment/proposal/request
identity, payload hash, original expiry and source-export lifetime/authority. It
never re-evaluates or refreshes a proposal. Source export deletion/expiry/revocation
also denies reports. Pagination retains the frozen public numeric offset grammar; every page
loads the immutable owner-bound record and reauthorizes it. Canonical JSON and CSV renderers/evaluator source remain unchanged.

No new MCQ proposal can be prepared from today's incomplete captures. Local tests
seed synthetic external records for read coverage. **No legacy importer or live
owner mapping was implemented**; preserved native records require an independently
reviewed offline translation or drain before cutover. Do not infer usable proposal
creation merely from this reader. D6 storage/retention/ownership and actual host
acceptance remain open.

### `read_assignment_grading_resource` — T22

Both the fallback tool and SDK resource reads use the same strict `sakai://`
resolver with no legacy business-route fallback. Current inline support remains;
current submission/Assignment attachment bytes are unsupported. Captured inline
artifacts/manifests and frozen proposal reports use the external pipeline above.
Wrong resource shapes/report names fail before HTTP. Reads enforce source scope,
owner, revision or expiry and stored-byte integrity, and never issue an academic
POST or start/resume capture. Full attachment fidelity, native role/live behavior,
legacy links/owner import and external durability remain open.

Source and fresh focused evidence for all five additions:
[external-capture cohort](external-capture-cutover-2026-10-19.md),
[capture workflow](../../../services/mcp/src/sakai_mcp/workflows/captures.py),
[selected grades](../../../services/mcp/src/sakai_mcp/workflows/selected_grades.py)
and [resource resolver](../../../services/mcp/src/sakai_mcp/workflows/resources.py).

## Stable roster identity gate — B7, T04/T10/T11/T12/T20

The actual native `chef_assignments_instructor_list_submissions.vm` no-submission
branch renders a display name and blank cells, **without a stable UID, photo or
grading link**. Exhausting pages cannot establish who those missing students are.
Do not join by name or position. The synthetic empty-list fixture has been corrected;
without positive individual identity evidence, current source hydration fails
unsupported before requesting the Assignment item. A list containing only missing
rows therefore cannot produce a fabricated empty complete roster. Group/anonymous
privacy preflight remains in force.

A separately researched, authorized eligible-submitter roster with stable native
UIDs, active membership/role and submission eligibility is required to close this
gate. Native serialization can still omit evidence; attachments also remain blocked
on B8 scoped delegated Content access, ACL and byte/MIME integrity. MCQ preparation
continues to refuse incomplete captures. No full roster or attachment-byte claim
was added by the pagination improvement.

## Closing and maintaining limits

A limit is resolved only when its implementation and focused permission/identity/
contract tests support the stronger claim. Keep local evidence separate from
actual native per-role/delegated acceptance and deployment. Update this reference,
coverage, progress and the canonical plan as applicable; retain dated evidence as
history. Priorities remain B2 exhaustive announcement enumeration, B3/B7 scoped
metadata/complete roster evidence, R01 attachment scope/integrity, D3 concurrency
acceptance and D6 private-store acceptance. No limit is resolved by broadening
native permissions, adding replacement business endpoints or hiding uncertainty.

## Operation receipt default — T17, 20 October 2026

`get_assignment_grading_operation` now reads owner-bound external commit receipts
and reauthorizes the current site-wide individual Assignment targets through
existing HTTP. It preserves the historical timestamp, stages and unknown outcome;
it does not reconcile authorship from present grades. Historical Gradebook scores
are withheld as null with an explicit warning because current item/student
permissions are not established by this read. Required warnings never silently
truncate original warnings; over-budget receipts fail unsupported.

The configured durable store is required before any HTTP. Receipt/request hashes,
ID/kind/mode/row membership and owner/expiry are checked. Reads neither change
storage/expiry nor send an academic POST, resume pending work or retry a send.
Missing, expired, incompatible or unimported legacy records never fall back to a
native business route. Current scope uses the T10/T11 submitted individual subset;
withdrawn/missing/anonymous/group-only targets can fail reauthorization.

Current save/release defaults now use the existing Direct grading action for the
subset below. The earlier transitional native writer description is historical.
Prepared/Sending and stored historical outcomes retain their external record
format. Repeated IDs read without sending; different payloads conflict. Pending
records never resume automatically. D6 durable backend/retention/legacy ownership
and actual-role/live acceptance remain unresolved.

## Existing HTTP save, release and preparation — T14/T15/T18

**Actual defaults replaced locally, limited functionality; no live acceptance.**
The original facades use `workflows/grading_writes.py`; T18 keeps its exact frozen
canonical hash and commit arguments and calls read-only Python advisory validation.
Validation performs no academic POST or journal mutation.

- Exactly one submitted individual site-wide points row, integer displayed score,
  English locale, editable Assignment and existing instructor/item-edit authority.
  Group-only TAs, groups/anonymous/peer/review/rubric/tag/calendar/attachment and
  unsupported policy variants fail before mutation. Assignment must have an
  observed enabled Gradebook control switched off; linked or multi-Gradebook
  assignments are unsupported. No Gradebook score writes or projection guarantee.
- All overwritten private notes, feedback text/comment and resubmission/extension
  properties must be observable and exactly preservable. Plain ASCII text only;
  HTML, unsafe controls, trimming/Unicode transformations and missing/incomplete
  properties fail before POST. Preserve feedback, clear feedback and plain-text
  replacement are supported. Native submission/feedback attachments are not added;
  the existing action retains them. Complete attachment evidence remains unknown.
- Use T19 `list_assignments` or T16 `get_assignment_grades` Assignment metadata
  revision, T11 current grade revision or T16 composite grade/release revision,
  and current content revision. Each accepted row projection is checked separately;
  released/returned rows are rejected. T09's native semantic revision is rejected.
  Preparation reserves nothing; changed observations can invalidate later commit.
- `gradeOption=save` saves an unreleased row without native retract semantics;
  `gradeOption=return` performs native return/release and existing notifications.
  Release requires the current score and feedback digest; it is a separate intent.
- A configured durable external journal is required before commit HTTP. After
  Prepared/Sending, current actor/form/content/grade/private fields are rechecked,
  then exactly one URL-encoded POST to `/direct/assignment/setGrade.json` occurs.
  A race between the last read and POST remains possible. Neither the journal nor
  read revisions provide native CAS, row locks, transaction or batch atomicity.
- Post-readback checks assignment/form identity, score, release/returned flags,
  content revision, side fields and properties (except native `last_graded_date`).
  A successful observation is always `outcome=partial`, stage `saved` or
  `assignment_released`, with Gradebook score null and explicit warnings. It is
  not a causal receipt or full-state fidelity proof. Concurrent unseen state or
  notification delivery cannot be certified.
- Lost/invalid replies, mismatched post identity, uncertain transport/server errors,
  post-readback failure or journal persistence failure remain unknown. Repeated
  operation IDs read their historical outcome and never replay/resume, including
  pending records. A new ID is a new academic intent, not safe recovery.

Resolution gates: D3 rendered native grading/notification/field-preservation and
concurrent-edit acceptance; D6 durable backend/retention/legacy record ownership;
D8 matching native authentication, real roles/locales/configuration and deployment.
Widen batches, decimal precision, linked Gradebook, alternate policies or roles
only after their semantics and evidence are established. Source, synthetic facade
checks and preserved retirements: [grading write evidence](grading-write-2026-10-20.md).

## Additional context/MCQ evidence and helper retirement — 20 October 2026

Counts remain 20/22 local default replacements and 22/23 retired native routes.
T09 still cannot populate required raw native scale/release fields from the
researched existing projections. Warnings do not permit fabricated required values.
T20's current partial manifest is rejected before context/evaluation or proposal
persistence; its existing external frozen-proposal reconciliation remains useful
but was already implemented and is not counted again.

The modern Direct `assignment/gradable` action computes allowed/visible users but
returns only stored submission maps, not a complete no-submission roster. Generic
membership responses expose stable identities under separate native roster authority,
with privacy/user-directory omission behavior and a start/limit loop that is not
safe completeness evidence. Role-permission reads require site maintainer authority
and do not themselves reproduce Assignment-reference realm eligibility. These are
research candidates; no broader delegated route or membership fallback was activated.
Do not join no-submission rows by display name or assume a named role is eligible.

Four now-unused native mutation helper methods and their unused collaborator
injections were removed after caller review. Context link/capability/evidence
mapping and native metadata hashing remain unchanged. D7 factory/hydration/version/
lock/store compatibility and D6 records/cleanup ownership still need review. See
[source review and checks](evidence-review-2026-10-20.md).

## Attachment handler proof and Roster2 candidate — 20 October 2026

Native handler characterization confirms exact bytes/MIME for a synthetic plain
text stream and that the configured default HTML filter leaves text/plain/PDF
unchanged. Other configurations can transform bytes. Native success can contain
a truncated stream or an X-Sendfile header with no in-process body; URL/cloud
resources can redirect. HTTP status alone does not prove complete raw evidence.

These tests use synthetic ACL/resource/storage collaborators; they establish
handler ordering and behavior, not effective-role permission correctness or an
accepted delegated AccessServlet chain. Content remains blocked in Python and
native credential reach, covered through actual method/resource facades and guard
regressions. No resource family is newly complete or counted as migrated.

The additional Roster2 get-membership candidate returns totals only after cached
membership resolution, directory omission, hidden-member, configured visible-role
and group filters. Optional pronunciation integration can make third-party calls.
Assignment-reference authorization includes an Assignment realm alongside context
realms, so site roles alone cannot certify eligible submission identities.
No new native roster route or credential reach was adopted. Exact evidence and
next chain/response-validation gate: [attachment proof](attachment-proof-2026-10-20.md).

## Recorded attachment audit failures — 20 October 2026

The positive delegated content-chain proof fails with HTTP403 before RequestFilter,
binder or AccessServlet is reached. Source also lacks delegated filters on the
Access servlet. Two actual servlet-to-content component cases pass with synthetic
session/ACL/resource/storage collaborators; they do not prove effective native
role grants or the rejected delegated context. The separate positive Python
readiness probes fail collection (`No module named tests`) and establish no Python
capability result. Exact failures and untouched probes are recorded in the
[audit](attachment-audit-2026-10-20.md). The user requested failures be recorded
without fixes; no implementation or failed harness was repaired. Passing normal
regressions does not override these outcomes. Counts/functionality remain unchanged.


## Fresh remaining-tool gate verification — 21 October 2026

Fresh source context is the separated `codex/tool-migration-development` line,
starting at `833e7c4dc3844e0ddc545d47e92989e87fdc7140`. Follow
`docs/DEVELOPMENT_WORKTREES.md` and the current role record; server authentication,
filter reach/order and the pinned client protocol belong to auth development.
This worktree cannot supply matching new server authentication by itself.

Five new actual SDK facade checks establish partial MCQ capture rejection before
context/evaluation/proposal persistence, the retained T09 native GET, sanitized
simulated403 without fallback, and rejection of missing raw scale/release fields.
They use synthetic HTTP, OBO/principal and memory-store fixtures. They establish
Python routing/contract gates, not token validation, servlet reach or native ACLs.
Fresh checks pass 566 Python tests, lint/format/types and 30 focused Java tests.
The unchanged positive attachment-readiness invocation again errors at collection
(`ModuleNotFoundError: No module named 'tests'`), exit2, zero executed probes.
No failed test, fixture, import or implementation was repaired. The historical
positive delegated403 remains a failure before RequestFilter/AccessServlet;
its auth-owned Java source is absent here and was not rerun or copied back.

Current dependency correction: T14/T15/T18 now use HTTP observation preconditions,
not T09's semantic revision. The remaining runtime context consumers are the public
T09 facade and the later T20 context read. Earlier revision-consumer descriptions
in dated reviews describe their checkpoint. After capture and roster gates, T20
also requires the evaluator's unchanged context `supported.prepare=true` and
matching configuration revision; the retained T09 facade forces prepare false.
This later gate is source-traced, not exercised with fabricated complete input.
A coordinated truthful context/provenance transition is still required.

A14's existing `assignment/annc` helper returns a raw Assignment containing
scaleFactor/releaseGrades/properties in the model, but temporarily grants an
asn.new advisor and has unproven relationship serialization/scope. It remains an
unadopted source candidate, not evidence that all HTTP fields are impossible or
that grade-only TA safety is established. No credential reach was broadened.

Counts remain **20/22 local actual defaults, 22/23 historical routes retired**;
T09 and T20 remain, no resource family is fully migrated, no new retirement.
Complete roster/content gates, unsupported attachment ACL/MIME/byte/source binding,
D3 concurrency, D6 durable backend/legacy ownership and D7 ordinary UI retirement
remain open. Nothing is deployed, activated or live by these checks. See
[proof results and next gates](tool-proof-2026-10-21.md) and the new development-line
preservation record; old baselines, archives and continuation records are unchanged.


## Remaining-tool implementation attempt — 21 October 2026

T09 now has an actual existing-HTTP facade for a narrow instructor/edit-authorized
individual nonanonymous points subset, including a required explicit raw scale
(power of10, at most1e9), release flag, fields/properties and recognized edit form.
Raw Assignment attachments/groups/deleted/draft/peer/content-review variants and
missing required fields fail. It requires asn.grade, asn.new, asn.revise and
Gradebook item-edit authority; grade-only or group-only TAs cannot use this subset.
A14 raw relationships are bounded authorized instructor over-fetch, with actual
native entitlement/lazy serialization/delegated acceptance still open. Public
httpctx1 revisions are observations and incompatible with write preconditions.
Roster counts remain null; completeness and prepare/save/release false; independent
Gradebook link unknown. No full-context/role parity is claimed.

T20 now has no native context dependency; its evaluator metadata is separate from
the strict T09 response. Complete site-scope captures and complete stable roster
pages, content revisions, exact ID coverage, fresh existing source metadata and a
supported edit form precede evaluation. Current captures/rosters remain incomplete;
no successful current-source MCQ preparation or attachment acceptance is claimed.

The full suite has567 passes and17 failures. These are preserved without repair:
15 receipt fixtures reference removed _send,2 host tests lack the new submissions
client dependency. Focused21 tests pass; actual raw-model codec1 test passes.
Thus21 facades are wired, but only the preceding20 replacements have their prior
regression status. T09 is unaccepted; T20 is still incomplete;22/23 native routes
remain retired. The last native route is retained without a current Python caller.
See [exact evidence and failure categories](remaining-tools-2026-10-21.md).

## User-directed MCQ retirement — 21 October 2026

T20 is retired from the public catalog, not completed or accepted. Its earlier complete-roster/content requirements remain historical gates for the discontinued server workflow. Client assessment still requires complete, verified selected evidence and cannot infer class absence from incomplete listings. No attachments, extraction accuracy or filesystem delivery were accepted by this correction. The frozen evaluator/report implementation remains only for historical provenance verification; no runtime workflow imports the evaluator. Legacy proposal/report readers preserve existing expiry, authorization and stored records.

The retained payload helper does not grade; save/return use explicit approved scores with no required proposal ID. Current single-individual/integer/unlinked/English-form restrictions and non-CAS observation semantics remain. The service publishes broad historical schemas, so discovery alone does not establish bulk or decimal capability.

## Proof refresh — 21 October 2026, after count correction

The two catalog expectations are now18/21; default5/setup8 and all frozen contract/evaluator/report bytes are unchanged.585 normal Python and31 focused native tests pass. Prior17- and2-failure reports above remain historical, not current failures. This new regression evidence does not establish positive attachment readiness: unchanged external probe collection still fails on `tests`, and unchanged Skill validator still fails on `yaml`. No failing probe was fixed. Actual delegated AccessServlet proof source is excluded; the historical403 is not a fresh ACL denial. Exact current outcomes and proposed separate fixes are in [proof-refresh-results-2026-10-21.json](proof-refresh-results-2026-10-21.json) and the accompanying report.
