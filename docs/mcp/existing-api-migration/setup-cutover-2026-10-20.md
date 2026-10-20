# Practical setup cutover — 20 October 2026

Local work in `/Users/burhanahmadkhan/Desktop/sakai-mcp`, branch
`codex/replace-custom-sakai-api`, unchanged HEAD `0f9f44a7`. Initial scope/progress
and Git checks passed against the saved continuation. The independent custom branch/
worktree and main remain at `208d69ac`; support/restructuring/migration commits
`062b2845` / `b168e8cf` / `d447ec4e` are preserved. No reset, clean, staging, commit,
push, Git reorganization, deployment, feature activation, Azure action, academic
operation, schema change, artifact/receipt cleanup or legacy import occurred.

The user prioritized a useful working subset and continuing independent tools
before eliminating every previous limitation. This permits local implementation
with explicit limits; it does not permit guessed flags, weaker authorization,
uncertain-write replay or new native business interfaces.

## Three actual default replacements

| Tool | Actual caller and replacement | Local functionality |
| --- | --- | --- |
| T06 `get_course_assessment_context` | public MCP tool → original `AssignmentOperations` → `AssignmentSetup.context` | Native list/edit metadata/revisions, category selector identities, metadata-only Gradebook items/category rules and observed capabilities. Full Assignment/configuration and Calendar sections remain unavailable. |
| T07 `create_assignment` | public tool → original create validation/facade → `AssignmentSetup.save` | Native Add form, source-defined date-picker fields, configured external journal, one save/post, native-ID/publication/field readback and optional existing-native external Gradebook integration. |
| T08 `publish_assignment` | public tool → original facade → same shared workflow | Known visible/editable draft, fresh form observation revision, preserved rendered controls, one post and explicit partial verification. No repost/resume of already posted records. |

The original Python client constructs this workflow by default. Its Assignment
facade no longer receives or calls the legacy business transport, and unused custom
response parsing is retired. There is no alternate client/selector/legacy fallback.
The existing setup gate remains false by default, all four catalogs/descriptions/
strict public schemas are frozen, and no feature was activated. **16 of 22 tool
defaults are now replaced locally; six remain.** This counts implementation routing,
not full functionality, live acceptance or a deployed usable catalog.

## Existing interface research and practical scope

Source authorities:

- `AssignmentAction.java`: native add/edit/list state, `doAssignment_form`, save/post,
  `putTimeInputInState`, native Gradebook/Calendar/announcement staging and rubric/tag
  handling. Normal post does not provide old custom private-first or CAS guarantees.
- `chef_assignments_list_assignments.vm`: exact native Assignment references,
  draft-highlight versus view/edit title link, separate edit action and native pager.
- `chef_assignments_instructor_new_edit_assignment.vm` and `instructor_new_edit/`
  templates: actual successful controls, CSRF, 100-character title, grade/submission
  enum choices, audience, resubmissions, linked choices, features and shadow components.
- `SakaiDatePicker.js`: explicit `add-hidden-fields` with prefix + year/month/day/hour/
  min. Python reproduces only these source-defined fields; no general JS execution.
  Native `putTimeInputInState` interprets local components in the acting user's zone.
- `morpheus/tool.vm` → `includeStandardHead.vm` and `BasePortalHandler`: literal
  current-user UID/EID/site/effective timezone/locale. Python parses only bounded
  header literals and verifies identity, rather than trusting request timezone as
  native preference or changing the profile.
- Existing `GradesController.getSiteCategories`, `GradingServiceImpl.getAssignments`
  / `getAssignmentDefinition` and `CategoryDefinition`: `/grading/item-data` returns
  item/category metadata; native edit-or-grade checks govern its list. It may initialize
  Gradebook backing state. Setup never calls a student score or hydrated submission
  endpoint, or opens the Gradebook score table. Existing Assignment setup Skill caller
  constraints were traced; no Skill policy or academic approval requirement was changed.
- `AssignmentToolUtils.integrateGradebook` / `GradingServiceImpl.addExternalAssessment`:
  native external item creation defaults released/counting. `GbGradebookData.loadColumns`
  treats uncategorized items as uncounted when categories are enabled. Unsupported
  requested transient/private flag policies are rejected before mutation.

Supported writes: individual/site-wide points assignments, five public submission
modes, draft/posted creation and draft publication, finite minute dates, native-zone
conversion, resubmissions 0–10/unlimited (non-electronic 0), no attachments and no
linked calendar deadline. English numeric locales only; unsupported instants/aliases/
DST ambiguity and native field bounds fail before send. New-form optional calendar/
auto-announcement defaults are unchecked for an explicit none policy; forced/detected
unsupported review/anonymous/peer/rubric/group variants fail. Publishing rejects
JS-synchronized tag/rubric controls instead of clearing unknown associations.
Native rubric handling skips updates with no rubric parameters; no replacement
native business behavior was added.

Gradebook mode none, or native new_external with released=true/counted=true, is
supported. Category choices must be actual rendered IDs; visible category choices
plus uncategorized counting conflicts fail before writing. Item-edit authority and
metadata authorization precede an external-create POST. A visible conflicting item
title fails early; post-readback identity uses exact external Assignment reference,
app, item and category, never title. Unknown flags/settings remain unknown. Stored
item flags do not certify complete effective course-grade calculations.

## Partial results are deliberate

The frozen full Assignment object requires unexposed release/deletion/integration
state. T06 therefore reports its full Assignment section unavailable and supplies
labelled ID/title/draft/revision metadata in warnings, at most 500 rows and first
20 form revisions over at most 20 native pages. Category ID/name choices are similarly
labelled; complete native category rules are returned when actually exposed by the
metadata DTO. Missing flags/rules omit that full object with an explicit ID warning,
never false/zero defaults. Settings and item due-date fields remain null. Calendar
is unavailable, not empty-proof. Native drafts/search/group scope can narrow lists.

After observing a saved ID, core fields and publication state, T07/T08 return
partial with assignment=null, a configuration_revision warning and retry_safe=false;
full strict state cannot be asserted. Native instruction normalization differences
require explicit saved-content review. A later Gradebook read outage/unsupported
projection preserves the known Assignment ID with unknown link state. Permission/
identity failures remain errors; previously observed IDs remain in the private
journal. These results do not authorize repeating create or blindly posting again.

Durable Prepared/Sending precedes one academic form POST. Lost replies, unknown
markup/IDs, native errors and uncertain outcomes never cause automatic replay.
There is no public setup idempotency key or setup-journal recovery tool. New calls
are new intents; hidden drafts and concurrent identical operations remain possible.
Before/after observations, metadata, preference and UI writers are not one snapshot;
`http1-` is not a reservation or native CAS. Inactive visible/resubmission date defaults
are excluded from the form revision, preserving usability without weakening active
field comparisons. D2 staging/recovery, D3 concurrency and D6 durable retention/owner/
legacy compatibility remain actual acceptance/release gates.

## Focused native retirement and preservation

Retired three routes: assessment-context, assignment-create and assignment-publish.
Removed only their two controllers and unused `McpAssignmentSetupService`, plus their
two dedicated test sources. The three retired sources and their original tests
are retained in Git/private checkpoints. `McpAssessmentService` is reduced to its
unchanged semantic revision calculation, still called by retained grading query/
evidence/mutation paths; ordinary domain services, auth, native lock/store/helpers,
version/schema, exports, proposals, receipts and cleanup ownership are preserved.
No other business replacement endpoint/service/model/store was introduced.
The old `addDraftAssignment` factory now has no production caller; its interface,
implementation and two native regression tests remain recorded for separate D7
ordinary Assignment/API retirement review. It is not a fallback used by Python.

**19 historical routes are retired locally; four grading routes remain.** The
migration native tip cannot serve older Python clients that require retired setup
routes. Additive compatible auth → accepted Python HTTP cutover → separately
accepted native retirement remains mandatory.

Before editing, a verified owner-only **266-file** source/evidence archive was saved
under `/Users/burhanahmadkhan/Downloads/Sakai-Setup-2026-10-20/`. Direct copies of the
five retired source/test files and 19 individually removed stale generated class
files are preserved there. The existing integration guide was outside the selected archive
prefixes; its exact before bytes were reconstructed by removing only this increment's
appended section, verified against the pinned prior continuation, and saved in an
additional private before-record. Original manifests/archives were not rewritten.
No blanket clean or user/editor/data cleanup was used.
`continuation-2026-10-20-setup.json` pins the exact previous October 20 continuation
hash and explicit before/after paths. Earlier records, manifests and private archives
remain unchanged. Scope validation now accepts bounded named same-day increments;
prior hash/ancestry/mode/presence/index and frozen-contract checks remain enforced.

## Fresh local verification and next gate

- Locked dependency sync and `check-mcp.sh`: **535 Python tests**, Ruff lint/format (**123 files**), mypy (**70 source files**),
  frozen contracts/catalog/descriptions/evaluator/report checks pass.
- Real default-facade tests cover creation/publication modes, dates/timezone/locale,
  resubmissions, metadata-only category/identity/unknown-field scope, tag/rubric/group
  refusals, stale revisions, native normalization, single-send uncertain outcomes,
  journal-before-POST and known-ID preservation after Gradebook outages.
- Composed SDK/JWT/OBO test exercises context → draft create → publish through actual
  tool registration, plus student denial and existing read/resource/announcement
  paths. All native HTTP is synthetic source-derived fixture data, not live acceptance.
- Java 17 reactor: **47 tests in eight suites**, zero failures/errors/skips; actual
  auth/container/existing Sites/Login plus retained grading/wiring/retired-class checks.
- Fresh Java 17 package succeeds. WAR inspection excludes all **11** retired business
  controller/service classes and the obsolete metadata item-index inner class, retains
  grading mutation and the revision helper. `javap` confirms the latter exposes only
  its constructor and revision method.
- Fresh Python wheel/sdist, source-byte/content inspection, repository guidance,
  whitespace and required scope/preservation verification pass (recorded in progress).

No actual rendered Sakai instance, delegated role, native form mutation, notification,
category policy, deployment/config/schema/store inventory or runtime acceptance was
performed. Local results establish a useful implementation subset, not deployment.
Next work: grading-context/prepare-payload dependency group, broader setup Calendar/
attachments/flag support, stable eligible roster and complete content for MCQ, and
separately authorized native/delegated acceptance before any feature activation.
