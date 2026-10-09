# Assignment setup development release

Date: 8 October 2026. Status: **IN PROGRESS**. The owner authorized deployment and client use, explicitly authorized resuming the preserved environment and leaving it running, and authorized disposable synthetic course data without announcements. The owner also requested a local Discrete Mathematics MCQ PDF for their own client tests.

## Exact source and release identity

- Assignment implementation: `76fe89ff56c6237a7bdecbdb45e2b7ac3dec87f8`.
- Selected release: `f5807e93398e8a67b31f82bdba27148b26bcfb1f`, adding the refreshed pinned Python base and safe scanner diagnostics. Its `apps/sakai` tree is identical to the tested implementation tree (`d32e50799deef1cd353c12942b6b6bb93e25b529`). No database schema change is included.
- [Full Sakai build and delegated adapter CI](https://github.com/BuriAhmad/sakai-mcp/actions/runs/37819198467): PASS.
- [Repository, Python, Bicep, image and security CI](https://github.com/BuriAhmad/sakai-mcp/actions/runs/37819540179): PASS.
- [Exact-commit MCP digest deployment](https://github.com/BuriAhmad/sakai-mcp/actions/runs/37819783798): PASS.
- MCP digest: `acrsmcpdevo6wzl5rvdbkwc.azurecr.io/sakai-mcp@sha256:c56490c8cf3278530a5f32ff79079abb35c6fbd59bc136a235624ccffdc5a1c2`.
- Initial new MCP ready revision: `ca-mcp-sakai-dev--0000010`, with assignment gate still disabled during Sakai deployment.
- Previous MCP image for rollback: `acrsmcpdevo6wzl5rvdbkwc.azurecr.io/sakai-mcp@sha256:938b098240b403b2a40fc741edb49e72d85340cec040b78ab659fd3ebe02e51e`.
- Sakai guarded release: `20261008T180254Z-f5807e93398e`, VM build and local/public portal health passed. Previous code record is retained by the guarded release.

The first image scan rejected the old base with seven fixable high findings. With the updated official Python 3.11.17 slim-trixie digest, the source scan found zero high/critical findings or secrets. The built image had zero critical findings, zero fixable high findings, 44 high findings without published fixes, and zero secrets. This passes the existing development scan policy; it is not a zero-vulnerability claim.

## Runtime and client checkpoint

The selected Azure subscription was verified as `55a5701c-411e-45f1-9829-9c80f526d9eb`; all runtime actions target the existing `rg-sakai-mcp-dev` development environment. `./sakai start` returned a healthy public HTTPS portal, running VM/MCP, Ready MySQL, and private MySQL access. No resource recreation, capacity increase, OAuth registration/grant change, or runtime schedule change was performed.

Before the release restart, the normal tracked configuration script enabled `mcp.assignment.setup.enabled=true` with the verified existing Entra metadata. A separate pre-feature runtime properties backup was retained. MCP gate activation and assignment acceptance remain pending.

A separate disposable synthetic course named **Assignment Setup Sandbox - Discrete Mathematics** was created with native Assignments, Gradebook and Calendar backing tools. Existing instructor/student fixtures were added only to this new course. No existing course content was changed. Credentials, sessions, user IDs and created object IDs remain in ignored local test files, not this report.

The primary Codex configuration now includes the canonical Sakai endpoint, the existing pre-registered OAuth client and callback, and `default_tools_approval_mode="writes"`; its previous configuration was backed up. Its interactive login is separate from the existing authenticated test client. The Skill is installed in both the primary profile and the authenticated test profile. Fresh native client tool/Skill discovery remains pending until the repaired release is enabled.

The requested PDF and test prompt guide are in the ignored `services/mcp/codex-host-test/` folder. The two-page PDF was rendered and visually checked; it has 10 MCQs and a final requirement for `<roll-number-or-ID>.txt`, exactly 10 lines, and one lowercase a/b/c/d option per line. No answer key or course mutation authority is embedded.

## Acceptance and limits

Runtime creation/promotion, native Student by-ID/list draft privacy, owned item/deadline counts, replay/concurrency, native UI interoperability, and client discovery must be measured after the Sakai release becomes healthy. No assignment acceptance PASS is claimed at this checkpoint. Existing V1 Phase 25/31 host-control gaps are not closed by this release or by a non-model native catalog check.

The [local checkpoint](assignment-setup-local.md) and [design](../../SAKAI_ASSIGNMENT_SETUP.md) retain the implementation limits: no atomic cross-service commit, no exactly-once initial create, no automatic retry of ambiguous writes, no local PDF upload, no scheduled/email announcements, no unrelated item association, and unknown course timezone provenance. Standalone Gradebook/Calendar tools remain deferred. Advanced category/drop/resource/group scenarios and live fault injection require their own evidence.

## Live setup and replay repair checkpoint

The enabled revision `ca-mcp-sakai-dev--0000011` was Healthy with 100% traffic. Eight-tool discovery, new read/write annotations, V1 delegated course reads for instructor/student/outsider principals, instructor assessment metadata and student/outsider context denials passed. The fixture context correctly discloses permission-scoped other-author drafts; it does not claim complete conflict discovery.

Two synthetic assignments were created only in the disposable course. Valid Student/outsider creates were denied; invalid dates and duplicate title were rejected without another Assignment. Posted create verified point scaling, owned Gradebook/deadline links, requested release/count flags, no submission-score release and no native automatic announcement. Private draft had no integrations. Ordinary native Student login verified denial by ID, omission from lists/UI and access to the open posted Assignment. Ordinary native Instructor login verified the posted Assignment and owned item in the native Assignments/Gradebook UI. These native actors are existing synthetic fixtures added only to this new course; they are separate from the MCP delegated principals.

Two concurrent known-draft promotions produced one complete result and one revision conflict, leaving exactly one owned item/deadline for that Assignment. Identical posted replay then returned an unexpected conflict, despite identical observed metadata and linked references. A local regression reproduced Java JDBC `Timestamp.equals(Date)` inequality for equal instants. The coordinator now compares epoch milliseconds and still rejects changed due instants. Both added regressions and all 45 scoped WebAPI/login/MCP tests passed locally. The original native Assignment/Gradebook regression suites remain unchanged.

The MCP assignment catalog was paused again (`ASSIGNMENT_SETUP_ENABLED=false`) during repair. Existing V1 remained available; no test object was deleted or recreated. The guarded second Sakai release is pending CI and sufficient VM disk space. Before cleanup, free space was 7.7 GiB, below the release's 12 GiB minimum. No current release, rollback backup or data has been removed.

The Skill was installed into both the primary and test Codex profiles using Skill Installer with self-contained contract/client constraints. Post-repair native client catalog/Skill discovery remains pending at this checkpoint.

The replay repair is pushed as `98cbc53e60e440b5dc075c6fc046d8290c90139e`. Its [repository CI](https://github.com/BuriAhmad/sakai-mcp/actions/runs/37826901841) passed. Its [full Sakai CI](https://github.com/BuriAhmad/sakai-mcp/actions/runs/37826901851) passed. Cleanup permission is pending for only the generated source/build directories in older releases `20260924T181142Z-e0553fef88a0` and `20260924T190514Z-0bf7f762c563`, approximately 4.1 GiB each; their rollback backups and release records are explicitly excluded.

Primary client OAuth persistence was repaired on 9 October; see [the authentication evidence](sakai-oauth-persistence.md). The five enabled V1 tools and installed Skill are discovered in a fresh native process. Assignment tools remain disabled pending the separately authorized disk cleanup and guarded replay-fix release.
