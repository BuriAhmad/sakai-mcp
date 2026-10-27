# Native attachment handler proof — 20 October 2026

This increment adds reproducible local characterization and rejection tests. It
makes **no new actual default replacement**: totals remain 20/22 defaults and
22/23 historical business routes retired locally. T09/T20 and full resource-family
acceptance remain open. Content and roster routes were not adopted or activated.

## Preserved state

Before editing, verified required scope/progress checks and created an owner-private
checkpoint at `/Users/burhanahmadkhan/Downloads/Sakai-Attachment-Proof-2026-10-20`.
It contains 75 manifest paths and a verified 71-file source archive. Four editor
files were fingerprinted and excluded from the archive. The new continuation pins
the exact evidence-review predecessor. Original manifests, archives, baseline/start
and historical continuations remain immutable. No extraction over the checkout.

Migration branch/HEAD remain `codex/replace-custom-sakai-api` /
`0f9f44a76f34777b52f56ae03634ffd3a0b3bc6c`. Independent custom worktree remains
clean on its original branch/HEAD `208d69ac624910a29a7529934ddcc18bbac853e8`;
main remains there. Index is empty. No reset/clean/stage/push/branch reorganization.

## Existing handler behavior: tested, not inferred from HTTP status

`ExistingContentAccessTest` invokes the unchanged
`BaseContentService.handleAccessResource` implementation. Resource, ACL decision,
storage and session collaborators are synthetic; it does not prove actual native
role grants, resource availability or cross-context delegated integration.

| Case | Observed result |
| --- | --- |
| Plain-text stream containing CRLF and non-ASCII UTF-8 | Exact byte array, native `text/plain; charset=UTF-8` and length. No decode/re-encode. |
| Native `allowGetResource` denial | Permission exception precedes resource/filter read; no bytes. |
| Copyright agreement required | Copyright exception precedes filtering; no automatic acceptance. |
| Output-filter wrapper substitutes content | Delivered bytes can differ from stored resource bytes. |
| Truncated source stream | Handler can return HTTP 200 and the original Content-Length despite shorter body. |
| Storage direct URL | Redirect outside Sakai, no file stream. |
| Stored URL resource | Redirect to URL body, no file stream. |
| Storage sendfile mode | HTTP 200 with X-Sendfile and expected length but no in-process body. |
| Actual default `ContentFilterServiceImpl` + `HtmlPageFilter` | text/plain and PDF resources are returned unchanged by that filter. |

`BaseContentService` checks native `allowGetResource`, obtains the resource again
through native `getResource`, checks copyright, wraps filters and then performs
stream/redirect/sendfile logic. Ordinary native handlers, permission/model/schema
code and their behavior were not changed. The ACL tests stub the decision and
assert its enforcement/order; they are not tests of effective role computation.

Source locators:

- `kernel/kernel-impl/.../content/impl/BaseContentService.java`:
  `handleAccessResource`, `allowGetResource`, output filter/stream/copyright branches.
- `kernel/kernel-impl/.../content/impl/ContentFilterServiceImpl.java`:
  configured wrapper iteration.
- `kernel/kernel-impl/.../content/impl/HtmlPageFilter.java`: `isFiltered`, `wrap`.
- `kernel/kernel-impl/src/main/webapp/WEB-INF/content-components.xml`: default
  HtmlPageFilter registration. This source configuration is not a live inventory.
- `access/access-impl/.../AccessServlet.java`: BasicAuth, native entity dispatch,
  copyright session acceptance and separate secure-token branch. The latter uses
  a security advisor; a future narrow delegated path must reject securetoken and
  all copyright-accept/login/helper parameters rather than invoking that branch.

## Guarded existing defaults

A new `DelegatedChainTest` case verifies that the currently unaccepted `/access`
content context is rejected before verifier/account binding, for attachment and
group content paths. Production credential reach and servlet registrations are
unchanged. No native business dependency was added to the auth runtime.

Three new Python tests exercise the actual `ExistingApiTransport.content` method
and R01/R02 resource facades. They reject unaccepted attachment requests before
OBO/HTTP, with no custom business fallback. The `CONTENT` operation descriptor
remains blocked. Native handler characterization alone does not accept this route.

The two new Maven dependencies (kernel-storage-util and json-simple) are test-only,
needed to load the existing kernel handler/filter classes. The runtime dependency
allowlist still passes; proof/test dependencies/classes are absent from the auth
JAR. No production Java or Python implementation changed in this increment.

## Additional roster evidence

`RosterSiteEntityProvider.getMembership` provides an existing
`roster-membership/{site}/get-membership` candidate with page/pageSize/all controls
and total count. This avoids assuming the generic membership provider's pagination
semantics, but does not establish complete eligible students:

- `SakaiProxyImpl.getMembership`, `filterMembers`, `filterHiddenMembers` and
  `getAndCacheSortedMembership` filter by native roster/group/hidden authority,
  configured `roster2.visibleroles`, active directory-resolved membership and cache.
  `membersTotal` is the already-filtered list length, not all eligible students.
- Directory resolution failures can omit users. Optional Namecoach pronunciation
  configuration can make third-party requests while building roster data. No call
  was made and the provider was not adopted as a pure minimal metadata read.
- `AssignmentServiceImpl.getEntityAuthzGroups` includes the Assignment reference's
  own realm along with site/group context realms. `allowAddSubmissionUsers` calls
  `SakaiSecurity.unlockUsers` on that reference. Site role/function metadata alone
  is not proof of equivalent per-Assignment eligibility.

This is source research, not live/native-role acceptance. No display-name joins,
role-name guesses, total-count completeness inference or broader credential scope.
MCQ's complete roster/capture/evaluator checks remain unchanged.

## Fresh verification and next concrete gate

- Locked sync and full `check-mcp.sh`: **568 Python tests**, Ruff lint/format over
  **131 files**, mypy over **73 source files**. Frozen public contracts, catalogs,
  descriptions, evaluator fingerprint and report baselines remain unchanged.
- Explicit Java 17 focused reactor: **48 tests in nine suites**, zero
  failures/errors/skips. Includes nine native content cases and one additional
  guard case, retained grading/wiring, JWT/RequestFilter/Sites/Portal/Login cases.
- Fresh wheel/sdist and Java package builds pass. Wheel bytes match all Python
  sources and exclude editors. Auth JAR matches production class bytes and excludes
  proof/test libraries/classes. The WAR hash is unchanged from the prior increment;
  no native production implementation was edited or retired here.
- Required scope/progress/chained preservation checks, repository guidance and
  whitespace pass. Four editor fingerprints, private archive contents, original
  continuations, independent custom worktree/refs and empty index are preserved.

Logs: `/tmp/sakai-attachment-proof-native-final.log`,
`/tmp/sakai-attachment-proof-python.log`, `/tmp/sakai-attachment-proof-package.log`,
`/tmp/sakai-attachment-proof-wheel.log` (local diagnostics only).

Next local gate: demonstrate the delegated RequestFilter → **actual AccessServlet**
→ native permission/content path, with caller/selected-source identity binding and
negative role/ACL/copyright/secure-token/redirect cases. Then implement a bounded
plain-file subset with matching MIME/length, full-body checks, local digest and
fresh before/after source observations. Native filters/storage behavior and exact
raw-versus-delivered-byte semantics must be explicit; no complete MCQ capture or
stored-byte identity can be claimed merely from a successful response. Matching
native auth and Python cutover require separate real-role/configuration/release
acceptance before activation. No live or academic operation, deployment, feature
activation, Azure/runtime change or data/schema/record cleanup occurred.
