# Assessment context Calendar reference fix

Date: 13 October 2026 (Asia/Karachi). Status: **source fix implemented and verified; not deployed**.

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

The live MCP revision remains the previously deployed image. An MCP-only release of this fix can restore the read without rebuilding or restarting Sakai; the native producer correction can follow in a separately authorized Sakai release. Existing unrelated workspace changes must not be included accidentally in either release.
