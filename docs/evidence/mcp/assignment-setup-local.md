# Assignment setup — local implementation checkpoint

Date: 8 October 2026. Scope: local source and synthetic tests only. This is separate from V1 acceptance phases; it does not pass Phase 25 or Phase 31 and does not establish delegated runtime or host approval behavior.

## Implemented source

- Python bounded request/response models, timezone/date/window checks, fixed-origin delegated transport, strict response validation, structured partial outcomes and privacy-preserving partial audit classification.
- Opt-in MCP `get_course_assessment_context`, `create_assignment`, `publish_assignment`. The default catalog remains exactly the five V1 tools. `ASSIGNMENT_SETUP_ENABLED` defaults to false.
- Tracked configuration support: the Sakai script accepts a seventh true/false argument and preserves the existing gate when omitted; the MCP app Bicep template exposes a default-false `assignmentSetupEnabled` parameter. No configuration/apply command was run against Azure or the VM.
- Sakai metadata endpoint and placement-free assignment coordinator inside the existing bearer-filter namespace. `mcp.assignment.setup.enabled` defaults to false; disabled endpoints return 404 before domain access.
- Native `AssignmentService.addDraftAssignment` persists draft=true from the first insert. The by-ID availability predicate now requires non-draft for both open and visible date branches.
- Native `GradingService.isGradebookInitialized` checks backing-object existence without the lazy creation performed by ordinary getters. Native `GradingService.addExternalAssessmentUnreleased` checks assessment-edit permission and creates an external item unreleased and uncounted from its first persistence. Existing external add retains its original release behavior.
- Known-assignment promotion runs under a refreshed pessimistic database row lock in the Assignment service. This uses a database lock for promotion across processes; concurrent runtime acceptance remains pending, and it is not an exactly-once guarantee for initial creates or cross-service commits.
- The coordinator persists native Gradebook and owned Calendar references, disables score release, preserves known IDs on observed partial failure, and never creates announcements itself. The workflow Skill calls the existing announcement tool only after verified setup.
- Local draft promotion and identical posted replay reuse owned links. Posted partial recovery can apply the approved remaining Gradebook flags. A changed integration plan, stale revision, another author, unrelated item, group scope or unsupported native configuration is rejected.

## Local validation

Commands from the repository root:

```sh
uv run --project services/mcp --no-sync pytest -q services/mcp/tests
uv run --project services/mcp --no-sync ruff check services/mcp/src services/mcp/tests
uv run --project services/mcp --no-sync mypy services/mcp/src
JAVA_HOME=/opt/homebrew/opt/openjdk@17 mvn -f apps/sakai/pom.xml \
  -pl webapi,assignment/impl,gradebookng/impl -am \
  -Dtest='Mcp*Test,LoginControllerTests,AssignmentServiceTest,GradingServiceTests' \
  -Dsurefire.failIfNoSpecifiedTests=false test
```

The Python suite covers unchanged V1, opt-in discovery/schema bounds, invalid requests with zero transport, wrong-site results, bounded reads, single-attempt ambiguous writes, known partial IDs and audit redaction. Java tests cover disabled/denied endpoints, scaling, private drafts, no unwanted integrations, revision conflicts, metadata scope/budgets, owned item publication/recovery, owned deadline reuse after response loss, and source-backed draft privacy and initial external item flags. Final verification: **81 Python tests passed; 116 Java tests passed** (40 Assignment service, 33 Gradebook service, 43 WebAPI/login/MCP tests). Ruff and mypy passed. The Java 17 77-module dependency reactor completed successfully. Bash syntax, ShellCheck errors, the MCP app Bicep compilation, repository guidance, whitespace checks and Skill validation passed. Synthetic local property-file checks proved default false, explicit enable, omission preserving an existing true value, rejected invalid input with unchanged file, and original backup preservation.

## Remaining release gates and implementation limits

No Azure state, deployed catalog, Sakai data, OAuth registration or live course was changed. No client Skill was installed. Before enabling either flag, use a separately authorized exact-commit Sakai/MCP release and the disposable-course runtime matrix in `docs/SAKAI_ASSIGNMENT_SETUP.md`. Test actual instructor/TA/Student/outsider identity, native UI interoperability, student resource access, dates/custom scales, calendar initialization and commit intervals, multi-request locking, native task/event behavior, and host Allow/Cancel/persistent/autonomous controls.

Calendar can be visible before final posting; a row lock does not make Calendar/Gradebook/Assignment commits atomic. Transaction commit failures can still produce an ambiguous response, which must not be replayed automatically. No durable request marker or initial-create uniqueness mechanism was added. Title matching remains insufficient reconciliation when no ID is known.

Course timezone policy is unresolved. Context reports unknown provenance and uses a disclosed UTC default calendar window. Collection and byte budgets fail rather than silently truncating. Hidden drafts/groups and group Gradebooks are disclosed as permission-scoped. Metadata excludes student grades/submissions.

Existing resource references are checked for same-course ownership, current actor access, site-wide availability and ancestor scheduling/visibility. Actual Student read parity remains a runtime gate. HTML input is additionally limited to 65,535 UTF-8 bytes after native sanitization. Explicit offsets resolve repeated DST times; invalid zone offsets and nonexistent local times are rejected. Non-millisecond write instants are rejected rather than rounded.

Configuration-save failure retains the draft ID but may need manual repair: no general assignment editor is exposed. Missing links on a posted assignment require deliberate reconciliation rather than a create replay. Original local-file upload, scheduled/email announcements, unrelated existing-item association, standalone Gradebook/Calendar tools and unsupported grading/group/rubric/peer/plagiarism options remain deferred.

## Release preparation

The owner authorized deployment and client installation on 8 October 2026, then explicitly authorized resuming the preserved environment and leaving it running. The first exact-commit CI image scan rejected the earlier pinned base with seven fixable high findings. Release preparation updates both Docker stages to the official Python 3.11.17 slim-trixie image index digest `sha256:0dd364ba7e10242f07755449e3a3d0e35f9efd987952737b90def6709ab0c5ce`, verified from registry metadata on that date. Scanner diagnostics now print only blocked package versions and vulnerability IDs, never secret findings. Actual subsequent scan/deployment results must be recorded separately. The Skill now packages its own contract and client constraints for installation outside the repository.
