# Assignment setup development release

Date: 9 October 2026 (Asia/Karachi). Status: **DEPLOYED, ENABLED AND VERIFIED FOR DEVELOPMENT CLIENT TESTING**.

The owner authorized deployment/client use, explicitly authorized resuming the preserved environment and leaving it running, and authorized disposable synthetic course data without announcements. The requested local Discrete Mathematics MCQ PDF and test prompt guide are ready. This report records measured behavior; it does not claim full production acceptance or close outstanding Phase 25/31 host-control gates.

## Exact deployed versions

- Assignment implementation: `76fe89ff56c6237a7bdecbdb45e2b7ac3dec87f8`.
- MCP image source: `f5807e93398e8a67b31f82bdba27148b26bcfb1f`, refreshing the pinned Python base and safe scanner diagnostics.
- MCP digest: `acrsmcpdevo6wzl5rvdbkwc.azurecr.io/sakai-mcp@sha256:c56490c8cf3278530a5f32ff79079abb35c6fbd59bc136a235624ccffdc5a1c2`.
- Final Sakai repair source: `98cbc53e60e440b5dc075c6fc046d8290c90139e`.
- Final guarded Sakai release: `20261009T074027Z-98cbc53e60e4`. Full VM build passed in 10 minutes 55 seconds, followed by local and public portal health PASS. Its preceding application files are retained for `./sakai rollback 20261009T074027Z-98cbc53e60e4`.
- Initial assignment Sakai release: `20261008T180254Z-f5807e93398e`; its release record remains retained.
- Enabled MCP revision: `ca-mcp-sakai-dev--0000013`, Healthy/Running, latest and latest-ready revision equal. The existing ingress routes 100% to the latest revision.
- Both `mcp.assignment.setup.enabled=true` and `ASSIGNMENT_SETUP_ENABLED=true` were verified. Source/template defaults remain false; ordinary V1 remains five tools unless explicitly opted in.
- Previous MCP digest: `acrsmcpdevo6wzl5rvdbkwc.azurecr.io/sakai-mcp@sha256:938b098240b403b2a40fc741edb49e72d85340cec040b78ab659fd3ebe02e51e`.

CI passed: [initial full Sakai build](https://github.com/BuriAhmad/sakai-mcp/actions/runs/37819198467), [MCP/repository/image checks](https://github.com/BuriAhmad/sakai-mcp/actions/runs/37819540179), [MCP digest deployment](https://github.com/BuriAhmad/sakai-mcp/actions/runs/37819783798), [repair repository checks](https://github.com/BuriAhmad/sakai-mcp/actions/runs/37826901841), and [repair full Sakai build](https://github.com/BuriAhmad/sakai-mcp/actions/runs/37826901851). The repair changes only native Java replay validation; the deployed MCP service code is unchanged by that repair, so its previously scanned digest is retained.

The initial image scan rejected the earlier base with seven fixable high findings. After the official Python 3.11.17 slim-trixie update, source scanning found zero high/critical findings or secrets. The image had zero critical findings, zero fixable high findings, 44 high findings without published fixes and zero secrets. This satisfies the existing development scan policy, not a zero-vulnerability claim. The upstream dependency backlog remains separate from this development acceptance.

## Runtime and approved maintenance

The selected subscription was verified as `55a5701c-411e-45f1-9829-9c80f526d9eb`; runtime actions targeted only the existing `rg-sakai-mcp-dev` environment. VM and MCP are running, MySQL is Ready with private access. No resource recreation, database migration, capacity increase, OAuth registration/grant change or runtime schedule change was performed. Existing 0–2 MCP scaling is preserved. A separate pre-feature Sakai runtime properties backup is retained. Runtime remains running as requested.

The second guarded release required at least 12 GiB free; only 7.7 GiB was available. The owner permitted removing two proposed older source/build folders only if they had no future or unique project value. Each folder's 17,768 tracked files matched its exact retained ancestor commit on `origin/main`, with zero content/symlink differences. Each contained 152,162 generated files under `target`, `node_modules` or Sass cache, plus 200 generated skin outputs, frontend bundles and downloaded Node files defined by the tracked Maven/npm build. No unclassified differences remained. Rollback uses separate `backup/{webapps,components,lib}`, not these source trees.

Only `20260924T181142Z-e0553fef88a0/source` and `20260924T190514Z-0bf7f762c563/source` were removed. Their release records/logs and backups, current code, database and uploads were preserved. Git retains the exact source for future rebuilds. Free space became 16 GiB before deployment. The first older release retained its approximately 2.0 GiB backup; the failed second older release retained its original empty backup directory.

## Live fixture evidence

A disposable course named **Assignment Setup Sandbox - Discrete Mathematics** has native Assignments, Gradebook and Calendar backing tools. Existing delegated and native synthetic instructor/student fixtures were added only to this new course. No existing course content was changed. Credentials, sessions, user IDs and created object IDs stay in ignored private test files.

Measured checks passed:

- Exactly eight tool definitions: the five V1 tools plus `get_course_assessment_context`, `create_assignment` and `publish_assignment`; read/write and non-idempotent write annotations are correct.
- V1 delegated course reads for instructor/student/outsider principals; instructor assessment context; student/outsider context denials. The fixture context correctly discloses permission-scoped other-author drafts instead of claiming complete conflict discovery.
- Student/outsider create denial, invalid dates and duplicate-title rejection without an extra Assignment.
- Posted create with point scaling, an owned external Gradebook item and Calendar deadline, requested release/count flags, no submission-score release and no native automatic announcement.
- Private draft create with no integrations; native Student denial by ID, omission from list/UI, and access to the open posted Assignment. Native Instructor Assignments/Gradebook UI displays the posted Assignment and owned item.
- Two concurrent known-draft promotions produce one complete result and one revision conflict, leaving one owned item/deadline for that Assignment.
- After the repaired release, fresh identical replay of each of the two posted assignments returns `unchanged`; stale revision is denied. All known owned item/event IDs remain unchanged. Exactly two Assignments, two external items and two deadlines exist above baseline, with no score release or automatic announcement.

The initial posted replay found JDBC `Timestamp.equals(Date)` inequality for equal instants. The catalog was paused during repair, then the native coordinator was changed to compare epoch milliseconds while rejecting changed instants. Both regressions and all 45 scoped WebAPI/login/MCP tests passed locally; earlier 40 Assignment and 33 Gradebook tests remain unchanged. The final live replay results above verify the deployed fix. No assignment was deleted or recreated during repair.

## Client and requested PDF

The Skill is installed into both `/Users/burhanahmadkhan/.codex/skills/sakai-assignment-setup` and `services/mcp/codex-host-test/codex-home/skills/sakai-assignment-setup`. Both installed copies match the repository files, including self-contained contracts and client constraints. Fresh native Codex app-server processes in both profiles report OAuth, discover all eight tools and the enabled Skill. Both profiles' saved credentials successfully read instructor context for the sandbox. Native catalog checks used no model turn and do not prove model-selected write approval/cancel UX for the new tools.

Both profiles request the canonical MCP access scope plus `offline_access` and use file-backed OAuth storage; see [OAuth persistence repair](sakai-oauth-persistence.md). Each configuration has a private backup. `default_tools_approval_mode="writes"` remains enabled. Open a fresh chat or refresh the MCP connection to replace an older five-tool catalog.

The ignored test folder contains `services/mcp/codex-host-test/DM-MCQ-Assignment.pdf` and `ASSIGNMENT-SETUP-TEST.md`. The rendered, visually checked two-page PDF contains 10 Discrete Mathematics MCQs and final submission instructions: `<roll-number-or-ID>.txt`, exactly 10 lines in question order, one lowercase a/b/c/d per line. No answer key or invented schedule is included. The guide leaves **DM MCQ Practice** available for the owner's manual prompt test; that assignment has not been automatically created. Current tools can use the PDF as source instructions but cannot upload the local PDF to Sakai.

## Remaining acceptance limits

The 13 October CS 210 read failure exposed an ordinary Calendar event nullability mismatch. The [Calendar reference fix report](assessment-calendar-nullability-fix.md) records the targeted fix, regressions and verified MCP release to revision `ca-mcp-sakai-dev--0000014`. It supplements the measured 9 October release results; native producer normalization is committed for a future Sakai release.

The [local checkpoint](assignment-setup-local.md) and [design](../../SAKAI_ASSIGNMENT_SETUP.md) retain these implementation limits: no atomic cross-service commit, no exactly-once initial create, no automatic retry of ambiguous writes, no local PDF upload, no scheduled/email announcements, no unrelated existing-item association, and unknown course timezone provenance. Standalone Gradebook/Calendar tools remain deferred. Weighted/drop/custom-scale/resource/group cases, actual Student resource-read parity, live fault injection and new-tool model-selected approval/cancel/persistence controls need separate evidence. Existing V1 Phase 25/31 host-control gaps are not closed by this release. Use native course permissions and the approved Skill plan for client writes.
