# Existing HTTP discovery/read increment — 18 October 2026

Current branch: `codex/replace-custom-sakai-api`. This branch carries the whole
replacement/retirement plan. Authentication/session integration is one prerequisite;
it does not define or limit the branch's scope. HEAD remains `208d69ac624910a29a7529934ddcc18bbac853e8`
and the index is empty. Prior checkpoints and private archives remain intact.

## Capability work

- **B0 placement discovery:** Python now calls existing
  `/direct/site/{site}/pages.json` after fresh actor/course observations. It checks
  site/context/page/tool/placement identity and same-origin page URLs. It supports
  multi-tool pages, rejects duplicates/ambiguous placements, and never requests
  administrator `props`/`config`. The native page URL is not treated as a unique
  placement URL. Unsupported/missing placements are explicit; no tool installation
  or site mutation is attempted.
- **T03 announcement reads:** the public facade now supports explicit
  `ANNOUNCEMENT_READ_INTERFACE=existing`. It performs actor/native course visit
  checks before calling existing `/direct/announcement/site/{site}.json` with
  fixed `n=1000,d=3650,a=0`. Native permissions, message visibility and selected-role
  handling remain in the unchanged provider. Python discards merged/non-main rows,
  uses `announcementId` rather than the packed entity ID, preserves literal body
  bytes after JSON decoding and epoch-millisecond creation values, sorts stably
  and retains the existing maximum 50 output rows. Duplicate IDs, malformed shapes
  and a saturated 1000-row observation fail explicitly, without a legacy fallback.
- **Date compatibility:** source review found that Direct's `ViewableFilter`
  examines the release-date property rather than consistently limiting every
  posting date. Python therefore enforces the intended 3650-day posting window
  and excludes future posting timestamps. This deliberately implements the old
  reader's intended ten-year window, rather than reproducing its integer-overflow
  defect. It is not a claim to cover all history or every installation's native
  reorder/merged/selected-role behavior. Those parity cases remain acceptance gates.
- The default announcement read mode remains `legacy`. Creation remains on its
  transitional implementation until the rendered native Add/revise/readback flow
  is implemented and accepted. The new mode is local integration, not deployment
  or feature activation. Public tool/resource schemas and catalogs are unchanged.

## Authentication boundary work needed by these capabilities

The narrowly permitted native GET scope now also accepts site pages and the
existing announcement read. Only announcement parameters `n,d,a`, with one numeric
value each, are admitted there. Other reads still reject query/body input. Native
business handlers have not been changed.

Review of `SkinnableCharonPortal.showSession/showSnoop` and the generic
`morpheus/error.vm` found a potential diagnostic-body session-credential exposure.
Whether that specific template/context combination renders credentials on the
installed system has not been live-tested. Header suppression alone cannot prove
response-body secrecy. The auth wrapper now buffers the selected delegated responses
up to one million bytes, blocks the current native session credential in body or
headers, rejects opaque compressed/unsupported-character-encoding output, and
withholds unsafe output as an empty 502 response. Native flushes cannot emit a
partial body before that check. Unhandled downstream exceptions are sanitized
inside the auth boundary; cleanup still runs. No business HTML/JSON is parsed or
normalized in Java. This bounded wrapper is not yet a general large-file streaming
solution; content-resource authentication remains a later capability gate.

## Fresh local evidence

- Python: **360 passed**; lint, formatting and mypy pass (60 source files).
  `uv sync --locked` passes; wheel/sdist build successfully. Frozen public
  schema/catalog/resource/evaluator tests pass unchanged.
- Combined Java 17 reactor: **100 passed**, zero failed/errored/skipped: 23 auth
  module tests, 73 WebAPI existing/legacy/login tests, three existing Site pages/access
  provider tests, one existing Announcement provider/JSON-codec test. Actual
  RequestFilter and embedded Tomcat Portal dispatch continue to pass.
- The provider tests execute unchanged source with synthetic service doubles.
  They prove the tested native membership/page visibility, permission denial,
  returned relationships, draft exclusion and DTO/date-codec behavior. They are
  not deployed database/role acceptance or full rendered UI fixtures.
- The native auth JAR builds successfully. Scope/preservation verification and
  repository guidance checks pass; the original baseline/start hashes are not
  replaced. Current binary provenance is in `progress.json`.

## Retirement and next work

T01 and T03 now have local existing-HTTP facade modes. All 23 custom routes remain
because default/legacy callers still use them, and the shared course controller
contains both reads. Removing it now would break those callers. No code retirement
or data cleanup is claimed. Replace the remaining consumers and close each
capability's parity gate, then remove that capability's obsolete method/controller
and account for shared helpers under plan §0.3–0.4.

Next: implement the rendered Announcement Add/revise/navigation/readback workflow,
then Assignment/Gradebook views using the validated placement resolver. Close
public-nonmaintainer course visit proof, merged/role/date/reorder behavior and
ordinary login/OAuth/Basic/diagnostic handling against an authorized exact native
release before default cutover. D3 applies before enabling grading commits; it
does not prevent independent local read/browser/storage implementation. D6 remains
required before provisioning/import/storage cutover. No runtime, academic or
stored-data action was performed.

## Additional T01 parity work in the same increment

Published public courses now use explicit existing Direct `select=access` rows,
native non-deleted SQL selection and separately checked fresh effective visit
permissions. A public detail response alone remains insufficient. An ambiguous
masked false publication state is explicit, rather than silently removing the
course. Native selection remains ACCESS even for admins; the auth guard rejects
alternative selections or credential/query extras. This is source-confirmed and
locally tested, not a deployed SQL/role observation. Source: existing
`SiteEntityProvider.getEntities`, `DbSiteService.getSitesWhere`, and
`SiteServiceSqlDefault.getSitesWhere11Sql/getSitesWhereNotSoftlyDeletedSql`.

The bounded lookup advances by actual returned rows so a configured native page
cap cannot make a short page look like end-of-data. Empty pages, duplicate drift
and the 20-page limit are distinct. No snapshot/atomicity guarantee is claimed.
Per-course fresh lookups can be costly for large public-course inventories;
performance and native role/cache behavior remain default-cutover acceptance gates.
No long-lived access/soft-delete proof is cached in Python.

Course discovery preserves the old sorted first-500-visitable limit instead of
failing simply because more than 500 courses exist. Java UTF-16 comparison order
is retained for supplementary-character titles and IDs. Underlying rich-response
byte/5000-item bounds still fail explicitly if exceeded. Tests cover public member
success, missing native access, masked ambiguity, server-clamped paging, duplicate
and saturated inventories, the cap and Unicode ordering.

## Fresh read-only environment check

`./sakai status` verified the expected subscription on 18 October 2026 and reported
the Sakai VM **deallocated**, MySQL **Ready**, and MCP **Running** in the control
plane with min/max replicas **0/2**. The last value is not an actual replica count
or an endpoint acceptance result. Public Sakai HTTPS probing was skipped because
the VM is deallocated. No start/stop, capacity, deployment, feature activation,
firewall or academic action was performed. Actual installed native/schema/private
store inventory and delegated rendered-handler acceptance therefore remain open
under the user's runtime restrictions.
