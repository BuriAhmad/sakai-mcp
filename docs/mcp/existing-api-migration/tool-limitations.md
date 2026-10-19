# Known tool limitations

Reviewed against the local implementation on **19 October 2026**, branch
`codex/replace-custom-sakai-api`. This is the current limitations reference for
maintainers and tool consumers. The [canonical plan](implementation-plan.md)
governs implementation; [coverage](coverage.json) and [progress](progress.json)
record migration state. Update this reference whenever a limit is discovered,
changed or resolved, and link the implementation and verification evidence.

**Eight tools have local existing-HTTP replacements. This does not establish full
functional parity or live acceptance.** Fourteen tools still need migration, and
none of the five resource families is fully migrated. Local tests and package
builds do not prove deployed configuration, actual rendered native views, all
Sakai roles, notification delivery or production performance. Nothing in this
reference authorizes deployment, feature activation or academic writes.

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

## Shared transport, resource and release limits

Existing JSON responses default to a **1,000,000-byte** budget. Native HTML is also
bounded; unrecognized markup or missing/ambiguous placements and controls fail.
These bounds may reject larger legitimate courses/assignments before row caps are
reached. Browser navigation interprets only accepted rendered URLs/controls;
source-derived synthetic fixtures do not prove every customization or Wicket/form
variant. No arbitrary JavaScript or unknown native workflow is executed.

All five resource families remain incomplete. R01 submission files has existing
HTTP **inline support only**. Assignment files, captured export files/manifests,
proposal/report dependencies still require their own existing-HTTP migration and
legacy-record compatibility work. The public resource fallback tool is not proof
that every resource is migrated or every attachment readable.

Fourteen tools still require migration: `get_course_assessment_context`,
`create_assignment`, `publish_assignment`, `get_assignment_grading_context`,
`export_assignment_submissions`, `get_assignment_submission_export`,
`save_assignment_grades`, `release_assignment_grades`, `get_assignment_grades`,
`get_assignment_grading_operation`, `prepare_assignment_grade_payload`,
`prepare_assignment_mcq_grades`, `get_assignment_grading_proposal` and
`read_assignment_grading_resource`. Some coordinate replaced reads but still have
legacy business-route dependencies. In particular, MCQ preparation cannot bypass
the incomplete submission-evidence gate. Their architecture/concurrency/storage
acceptance is not closed by the eight replacements; consult the per-tool matrix
and D1–D8 decisions in the [canonical plan](implementation-plan.md).

The local native tip has retired **nine** historical routes and cannot serve older
Python clients needing them. Release ordering must remain compatible additive-auth
native revision → accepted Python HTTP cutover → native retirement. Rolling back
Python also requires compatible native route support. No deployed behavior should
be inferred from this local source state.

## Closing and maintaining limits

A limit is resolved only when its implementation and focused permission/identity/
contract tests support the stronger claim. Keep local evidence separate from
actual native per-role/delegated acceptance and deployment. Update this reference,
coverage, progress and the canonical plan as applicable; retain dated evidence as
history. Priorities remain B2 exhaustive announcement enumeration, B3/B7 scoped
metadata/complete roster evidence, R01 attachment scope/integrity, D3 concurrency
acceptance and D6 private-store acceptance. No limit is resolved by broadening
native permissions, adding replacement business endpoints or hiding uncertainty.
