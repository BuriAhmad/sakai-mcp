# Assessment context Calendar reference fix

Date: 13 October 2026 (Asia/Karachi). Status: **MCP fix committed, deployed and verified**. Native producer normalization is committed for a future Sakai release.

## Confirmed cause

The failing `get_course_assessment_context` calls reached the CS 210 assessment endpoint and received HTTP 200. A fresh read using the same saved delegated client profile reproduced the response validation failure: all 27 ordinary Calendar events supplied `assignment_id=""` and `owner_tool_id=""`. These were the only empty string fields in that response. No raw context, tokens or identities are included in this report or committed fixtures.

Native `CalendarEvent.getField` delegates to `BaseResourceProperties.getPropertyFormatted`, which returns an empty string when a property is missing. Ordinary events have no Assignment owner fields. The Python contract allows null for these fields but rejects empty references, so the returned course context was rejected and mapped to `INTERNAL_ERROR`. Course ID, dates, OAuth and native authorization were not the cause of these successful HTTP responses. Earlier acceptance used Calendar deadlines carrying owner fields and did not reproduce ordinary event behavior.

## Fix and related-code review

- The Sakai assessment producer emits null for absent Calendar assignment/owner fields.
- The Python Calendar event model normalizes those two empty fields to null before validation, allowing the existing Sakai deployment to work with a newly released MCP image. Actual owner references remain unchanged. Required IDs, invalid types and overlong references still fail validation.
- The other existing tool responses and the local gated grading implementation were checked for the same nullable extra-field getter pattern. No other response producer uses `CalendarEvent.getField` for optional references. Calendar link output used by create/publish reads the Assignment property map, whose absent values are already null. Gradebook and grading references do not use this getter. This is a targeted code review, not live acceptance of every write or every native data shape.

## Verification

- The exact live CS 210 payload validates with the fixed model; all 27 events are preserved and their absent references serialize as null.
- Python: **119 tests passed**, including new adapter regression coverage for mixed ordinary/owned events, null/empty absence, preserved owned references and rejection of invalid references. Ruff and mypy passed.
- Java: **66 WebAPI MCP/login tests passed**, including the new native producer regression using actual empty-string getter semantics. The dependency reactor build passed. This includes tests of the pre-existing local grading implementation; its feature gates and deployment state remain unchanged.
- `git diff --check` passed. Diagnostic response material remains in an ignored private artifact with mode 0600.

## Authorized MCP release

The owner explicitly requested committing and releasing the fix. Only its six source/test/evidence files were committed; the unrelated local assignment grading implementation and other workspace changes were excluded. A clean archive of the exact committed MCP source passed **88 tests**, Ruff and mypy. The larger local test counts above include that unrelated implementation and are not the released catalog.

- Source commit: `ea2f041d1d8e2ce7e91ff50bf20699f37f945a93`, pushed to `main`.
- [Repository validation](https://github.com/BuriAhmad/sakai-mcp/actions/runs/38348385220) and [exact-commit image check](https://github.com/BuriAhmad/sakai-mcp/actions/runs/38348385689) passed before deployment.
- [MCP digest release](https://github.com/BuriAhmad/sakai-mcp/actions/runs/38348521494) passed its repeated image scan, HTTPS health probes, OAuth challenge, resource metadata, image identity and revision readiness checks.
- Image: `acrsmcpdevo6wzl5rvdbkwc.azurecr.io/sakai-mcp@sha256:482f3c729ac4fe9bae93f87a12d660f584ca96155223b2b9f5aee531e1d53b00`.
- Ready/active revision: `ca-mcp-sakai-dev--0000014`, Healthy/Provisioned with one observed replica. Latest and latest-ready revisions match; `APP_COMMIT` matches the release commit. Assignment setup remains enabled and 0–2 autoscaling is preserved.
- Rollback image: `acrsmcpdevo6wzl5rvdbkwc.azurecr.io/sakai-mcp@sha256:c56490c8cf3278530a5f32ff79079abb35c6fbd59bc136a235624ccffdc5a1c2` (preceding revision `ca-mcp-sakai-dev--0000013`). Use the existing revision rollback procedure in `docs/MCP_RELEASES.md` if required.
- Source scan: zero critical/high vulnerabilities and zero secrets. Image scan: zero critical, zero fixable high, 44 high without published fixes and zero secrets, matching the previously recorded development scan policy.

Read-only authenticated acceptance used the same saved CS 210 instructor profile that produced the failing calls. The eight-tool catalog, course list and announcements read passed. `get_course_assessment_context` passed without a window (27 preserved events), with the original Asia/Karachi window (two preserved events), and with its equivalent UTC window (two preserved events). No empty owner references remain in the public results. MCP readiness and the Sakai HTTPS portal also passed.

Only the MCP image was released. The existing native Sakai response still supplies empty strings, which the deployed compatibility normalizer now accepts. Native producer normalization remains a committed correction for a future exact-commit Sakai release. No Sakai application release, database migration, course mutation, credential change or capacity change was performed.
