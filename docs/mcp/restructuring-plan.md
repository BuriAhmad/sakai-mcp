# MCP codebase restructuring plan

**Date:** 15 October 2026

**Status:** local structural implementation complete; deployment and container scans pending the release environment

**Starting revision:** `208d69ac`, plus the existing working tree

**Primary outcome:** a developer can locate a capability, trace its request, and change it without navigating unrelated workflows or knowing the project's implementation history.

## Implementation checkpoint — 15 October 2026

The agreed middle ground is implemented locally: one public tool-definition file, cohesive authentication/OBO/configuration/audit/validation modules, typed Sakai operation groups, extracted grading/resource workflows, and focused native grading services. Tests, shared CLI helpers, package selection, CI and contributor maps were updated with the source.

See [the verification record](../evidence/mcp/restructuring-local.md) for exact results and [the service README](../../services/mcp/README.md) for the final directory map. The native classes remain together within responsibility-based subpackages rather than introducing every illustrative nested package below. Existing native JSON DTO shapes were preserved; broader DTO conversion is deliberately separate. No Bicep or storage-layout change was needed. Runtime release and container security scans remain separate gates.

## 1. Scope and approach

Cover the complete project-owned MCP implementation: Python service, native Sakai integration, tests, operational scripts, CI, contributor guidance, contracts, and dependent Skills. Organize the Python service by responsibility: one discoverable MCP interface, explicit workflow logic, typed contracts, and Sakai integration code. Group domain operations within those layers where useful.

**Architectural decision:** keep all public tool definitions together in `mcp/tools.py`, backed by cohesive, independently testable implementation modules. Preserve useful existing boundaries such as `auth.py`, `obo.py`, `audit.py`, and setup validation. The target balances a discoverable API with modular implementation; neither the minimum nor maximum number of files is a goal. Skills do not determine application package boundaries.

The implementation covers the project-owned code discussed with the user. The repository also contains approximately 17,796 tracked files under `apps/sakai/`. Preserve upstream Sakai's Maven and package conventions; restructure the project-owned integration and review its modifications to assignment services without reorganizing the entire imported application. A wholesale upstream Sakai rewrite would be a separate project with a different maintenance cost.

Keep `services/mcp/`, `apps/sakai/`, `scripts/`, `deployment/`, `docs/`, and `skills/` as the repository's top-level ownership boundaries. There is no demonstrated need to relocate them. The main restructuring belongs inside those boundaries.

Deliver this work through independently passing changes. Complete the structural migration first, then remove temporary facades and tighten enforcement. Track behavioral fixes separately so reviewers can distinguish preserved behavior from intentional changes.

## 2. Verified starting point

These are local source observations, not claims about the connected endpoint or Azure runtime.

| Area | Observed baseline |
| --- | --- |
| Python implementation | 17 files, 3,734 lines under `services/mcp/src/sakai_mcp/` |
| Python tests | 19 files, 2,184 lines including helpers and package markers |
| Native MCP adapter | 14 Java production files, 2,271 lines in WebAPI's `mcp` package |
| Python test suite | `137 passed` |
| Ruff | `ruff check src tests` passes |
| Mypy | `mypy src` passes for 17 source files |
| CI | Existing shell, Bicep, Python, image build, and security scan jobs |
| Working tree | Existing modified documentation/ignore rules and untracked editor, evidence, and Skill files; preserve them |

Commands run from `services/mcp/`:

```sh
uv run --no-sync pytest -q
uv run --no-sync ruff check src tests
uv run --no-sync mypy src
```

Java tests, image scans, shell checks, Bicep compilation, and live acceptance were not run for this planning pass. They remain implementation gates where relevant.

### Problems established by source inspection

| Location | Concrete problem | Consequence |
| --- | --- | --- |
| `server.py` (230 lines) | Server construction, identity access, pagination, Sakai timestamp conversion, V1 tools, assignment setup, and feature registration share one module | Adding a feature requires understanding unrelated protocol and domain details |
| `sakai_client.py` (457 lines) | Shared errors, HTTP lifecycle, token exchange, retry/error rules, JSON requests, binary streams, setup verification, and grading endpoint dispatch share one client | Transport changes can affect every workflow; domain behavior is difficult to isolate |
| `grading_proposal_tools.py` (361 lines) | Decorated handlers also load exports, check artifact hashes, traverse roster pages, evaluate submissions, persist proposals, and render receipts | Workflow logic is coupled to MCP registration and presentation |
| `grading_resources.py` (404 lines) | URI parsing, resource discovery, SDK content conversion, public response decoration, manifest aggregation, report construction, and authorized reads are interleaved | Resource changes require understanding the whole grading pipeline |
| `grading_models.py` / `grading_resource_models.py` | Native REST contracts and MCP representations are already distinct, but names such as `Attachment` and `Assignment` depend on module aliases for meaning | Developers must repeatedly resolve `gm` and `rm`; careless consolidation could erase a real contract boundary |
| `grading_tools.py` | Tool-name strings drive invocation and write classification; request/result models live in another registry and routes in a third dispatch table | Adding an operation requires synchronized edits without a clear checklist |
| Principal handling / annotations | Principal lookup and tool annotation definitions repeat across registration modules | Similar operations can drift in authentication/error/annotation behavior |
| Tests | Some tests patch module-level `get_access_token`; another replaces `client._http` directly | Module moves break tests for implementation details rather than observed behavior |
| Native `McpAssignmentGradingService.java` (680 lines) | Authorization, roster construction, attachment reads, export capture, proposal persistence, score validation, save/release, and reconciliation live in one compressed class | Permission and transaction boundaries are difficult to review |
| Native Java style | Dense statements, wildcard imports, short names, and extensive `Map<String,Object>` construction | Important transitions and response fields are hard to follow |
| Runtime metadata / docs | Package and server versions are `0.2.0`, while the image label is `0.1.0`; some architecture text describes older catalog/acceptance states | Contributors cannot reliably distinguish current code, historical evidence, and runtime status |
| `sakai` / `scripts/lib/azure.sh` | The login dispatcher repeats the configured subscription ID; the shared Azure library also owns SSH/firewall helpers | Configuration and operational responsibilities have begun to overlap |

File length is supporting evidence, not the definition of a problem. Small cohesive modules such as `config.py` and `audit.py` can remain intact.

## 3. Behavior and compatibility that must survive

1. Preserve the five-tool default catalog and its names. Assignment setup adds three tools only when its flag is enabled. Grading adds fourteen tools and five resource templates only when its independent flag is enabled. Test all four flag combinations: 5, 8, 19, and 22 tools respectively.
2. Preserve tool descriptions, annotations, flattened arguments, required/optional distinctions, defaults, schema aliases, bounds, and outputs. Function signatures and Pydantic class names can affect generated schemas and `$defs` even when JSON values look unchanged.
3. Preserve `/mcp`, health routes, canonical OAuth discovery, stateless HTTP behavior, and the existing container entrypoint. `/live` and `/ready` must remain local checks without upstream dependency probes.
4. Acting identity comes only from validated delegated authentication. Maintain separate MCP and Sakai audiences, OBO exchange, native request-local sessions, and per-call site/object/group authorization.
5. Preserve fixed-origin requests, encoded identifiers, disabled redirects/environment proxies, bounded reads, timeout handling, and current concurrency budgets. No generic URL proxy or caller-selected acting identity.
6. Preserve exact retry and error behavior during extraction. JSON GET requests currently allow up to three attempts; POSTs are single-attempt. Binary reads have a separate path. A POST used for grade queries is semantically a read and has its existing special error handling. Do not simplify these rules by HTTP verb alone.
7. Preserve unknown/partial mutation outcomes, operation/proposal reconciliation, optimistic revisions, payload hashes, and separate save/return approval. A structural refactor must not replay academic or private-storage writes.
8. Preserve persisted export/proposal/operation record fields, ownership keys, native locks, expiry behavior, private storage layout, and `ASN_SUBMISSION.LOCK_VERSION`. No storage migration is expected.
9. Preserve canonical JSON, decimal serialization, row ordering, report bytes, and checksums. `evaluate_mcq` records `sha256(inspect.getsource(evaluate_mcq))`. Moving it unchanged can preserve the hash; changing its body, name, or formatting can change provenance. Freeze its source text during the mechanical migration and verify the actual fingerprint.
10. Preserve logging redaction, request correlation, safe error codes, synthetic test fixtures, and the distinction between implemented source, released code, and observed client acceptance.

## 4. Target Python organization

Keep the MCP interface together and separate it from implementation. For the maximum current catalog of 22 tools, one explicit tool-definition file is a reasonable starting point. All public names, signatures, descriptions, annotations, registration, and feature gates must be inspectable there. It must not contain the implementation of exports, grading, HTTP, or persistence.

This is a layered organization with domain grouping inside contracts and Sakai integration. It is not organized by Skills. A Skill describes how a client uses tools; changing a Skill must not require moving server code, and several Skills can use the same server capability.

The following map identifies actual responsibilities. Keep existing cohesive modules intact during initial moves and split them only where distinct responsibilities justify it. Include ordinary package markers where required.

### Preserve useful modularity

The existing `obo.py` is an example of a useful boundary: `asgi.py` constructs `OBOProvider`, and the Sakai client calls its `acquire` method for both JSON and binary requests. It owns certificate-backed token exchange and independent downstream validation. Keep that implementation together and inject it into transport. Document the established OBO acronym rather than renaming it merely to make the tree look uniform.

| Existing responsibility | Decision | Reason |
| --- | --- | --- |
| Inbound authentication in `auth.py` | Preserve as `security/auth.py` | Validating an incoming token has a clear contract distinct from obtaining a downstream token |
| Token exchange in `obo.py` | Preserve as `security/obo.py` | Cohesive security component shared by Sakai request paths |
| Settings in `config.py` | Preserve intact | One owner for validated configuration |
| Audit context in `audit.py` | Preserve intact | Shared request context, redaction, and outcomes belong together |
| Setup validation in `assessment_validation.py` | Preserve as `contracts/assignment_setup_validation.py` | Cross-field date/setup rules are cohesive and independently testable |
| Tool definitions spread across registration files | Consolidate into `mcp/tools.py` | One discoverable public interface, with short handlers |
| HTTP, route selection, and domain verification in `sakai_client.py` | Separate transport from named Sakai operations | Shared HTTP behavior and operation contracts change for different reasons |
| Proposal computation inside decorated tool handlers | Extract to `workflows/grading.py` and the pure grading engine | Complex orchestration can be understood and tested without MCP registration |

A new module should own a responsibility that can be named and described, have clear inputs/outputs, and simplify its callers. Reuse, independent tests, and a different reason to change support a boundary; a component need not be called twice to deserve one. Avoid splitting a small coherent operation across files or introducing wrappers that only forward calls.

```text
src/sakai_mcp/
  __init__.py
  asgi.py                           # stable deployment entrypoint
  bootstrap.py                      # construct and own runtime dependencies
  config.py                         # validated settings
  audit.py                          # request audit context
  errors.py                         # service error codes
  security/
    auth.py                         # preserve inbound token verification module
    obo.py                          # preserve certificate-backed OBO component
  mcp/
    server.py                       # construct SDK server, invoke registration
    tools.py                        # ALL public tool definitions and feature gates
    resources.py                    # resource templates and SDK read integration
    http.py                         # health and OAuth discovery routes
    context.py                      # authenticated principal and invocation errors
    presenters.py                   # native results -> public SDK results/links
  contracts/
    assignment_setup.py             # setup request/result models
    assignment_setup_validation.py  # preserve cross-field date/setup rules
    grading_native.py               # native REST request/response models
    grading_public.py               # MCP resource-enriched grading models
    grading_proposals.py            # frozen configuration/proposal/payload models
  sakai/
    client.py                       # own transport and typed operation groups
    transport.py                    # OBO-backed JSON/binary HTTP, limits/retries
    paths.py                        # encoded identifiers and fixed API root
    courses.py                      # course and own-grade operations
    announcements.py                # read/create and native result verification
    assignments.py                  # setup, publication, legacy submission metadata
    grading.py                      # native grading/export/proposal/file operations
  workflows/
    grading.py                      # proposal reconciliation, evidence, preparation
    resources.py                    # authorized resource resolution and URI handling
  grading/
    evaluator.py                    # pure MCQ engine; source frozen initially
    serialization.py                # canonical bytes and payload hashing
    reports.py                      # deterministic CSV/JSON report construction
```

### Why one tool-definition file is appropriate here

- A developer can inspect the entire public API without searching feature folders or tracing registration imports.
- Each tool defines its public signature and forwards to a named adapter operation or workflow. Shared invocation handles authenticated context, safe error translation, and audit consistently.
- The default five tools and independent setup/grading registration blocks appear explicitly together. The legacy submission metadata tool remains available with grading disabled.
- A long signature or description is interface documentation. Several hundred lines of explicit definitions can be cohesive; do not split them solely to satisfy an arbitrary file-length target.
- If this grows into independently maintained domains or becomes difficult to navigate after implementation logic is removed, split into `mcp/tools/courses.py`, `assignments.py`, and `grading.py` with one registration entrypoint. That is a future evidence-based choice, not a requirement now. Definitions would still all live under `mcp/tools/`.

For a simple read, the call path is `mcp/tools.py -> sakai/courses.py -> sakai/transport.py`. For a proposal, it is `mcp/tools.py -> workflows/grading.py -> Sakai operations + pure evaluator -> MCP presenter`. Do not add a pass-through service layer to the simple path.

Assignment setup coordination remains in native Sakai; Python validates and adapts its contract. A grading proposal needs a workflow because it coordinates several reads, integrity checks, evaluation, and persistence. These are distinctions in responsibility, independent of which Skill calls them.

### Responsibilities and dependency rules

| Component | Owns | Must not own |
| --- | --- | --- |
| `bootstrap.py` | Concrete settings, security, transport, adapters, workflow services, and app construction | Feature rules or tool response formatting |
| `mcp/` | All tool definitions, SDK registration/resources, authenticated context, protocol errors, annotations, presentation | HTTP request construction, roster traversal, grading decisions |
| `workflows/` | Proposal reconciliation, evidence collection, snapshot consistency, preparation limits, resource resolution | SDK `CallToolResult`, HTTP response objects, global server state |
| Sakai operation modules | Exact native routes, native response validation, feature capability checks | MCP decorators, public resource links, academic policy decisions |
| `sakai/transport.py` | Token acquisition, fixed-origin transport, limits, response integrity, retry/error translation | Tool-name dispatch, setup policy, grading presentation |
| Native contracts | Exact Sakai REST payloads and persisted-record representations where applicable | SDK resource links |
| Public contracts/presenters | MCP representations, SDK resource metadata, public formatting | HTTP or authorization bypasses |
| Evaluator / serialization / reports | Deterministic computation from explicit inputs | Network, filesystem, current principal, clock-dependent decisions |

Imports flow from composition to MCP handlers to workflows/Sakai operations to transport; contracts and pure functions sit below their consumers. Workflow code depends on a narrow typed grading gateway interface where a fake is useful. Do not create an abstract base class for every module. Transport cannot import operation modules or workflows; workflow and Sakai code cannot import MCP registration/presentation modules. There must be no production imports from `skills/`.

Introduce a validated identity wrapper only where it removes an actual SDK dependency from workflows. Bridge it from existing validated tokens internally and preserve all verification. It is request-scoped and must never become a tool argument, global user cache, or loggable token container. This can follow the initial mechanical moves.

### Complete migration map for today's Python files

| Current file | Destination / final responsibility |
| --- | --- |
| `__init__.py` | Retain a minimal package initializer; centralize version metadata without runtime side effects |
| `asgi.py` | Retain `create_app`; delegate wiring to `bootstrap.py` and retain health/discovery behavior |
| `config.py` | Retain; improve descriptions only where they aid configuration |
| `audit.py` | Retain; reference it through stable interfaces |
| `auth.py` | `security/auth.py`; preserve its cohesive verification implementation |
| `obo.py` | `security/obo.py`; preserve the OBO component, exception distinctions, and certificate handling |
| `server.py` | Server construction in `mcp/server.py`; all definitions in `mcp/tools.py`; invocation in `mcp/context.py`; result conversion in `mcp/presenters.py` |
| `resource_server.py` | `mcp/resources.py`; use constructor-injected resource resolver rather than assigning `grading_client`/`grading_enabled` later |
| `sakai_client.py` | `errors.py`, `sakai/transport.py`, `sakai/paths.py`, named Sakai operation modules; temporary delegating facade during migration |
| `assessment_models.py` | `contracts/assignment_setup.py`; retain class names/schema identity initially |
| `assessment_validation.py` | `contracts/assignment_setup_validation.py`; preserve its existing separation from model declarations |
| `grading_models.py` | `contracts/grading_native.py`; move transport operation registration out of model declarations |
| `grading_resource_models.py` | `contracts/grading_public.py` and `grading_proposals.py`; retain the native/public boundary |
| `grading_tools.py` | Definitions in `mcp/tools.py`; shared invocation in `mcp/context.py`; result conversion in `mcp/presenters.py` |
| `grading_proposal_tools.py` | Definitions in `mcp/tools.py`; workflow in `workflows/grading.py`; SDK receipt/resource content in `mcp/presenters.py` |
| `grading_resources.py` | SDK discovery in `mcp/resources.py`, domain resolution/URI handling in `workflows/resources.py`, SDK conversion in `mcp/presenters.py`, pure reports in `grading/reports.py` |
| `grading_evaluator.py` | `grading/evaluator.py`, `serialization.py`, and `reports.py`; preserve evaluator source text/fingerprint before later improvements |

### Operation routing and shared behavior

Replace unrestricted `grading_request(name, principal, request)` use with named, typed gateway methods. Keep a temporary dispatcher only while callers move. Each method owns its request/result types and route. All tool metadata stays together in `mcp/tools.py`; do not build a reflection-driven universal registry that mixes route construction, schemas, annotations, and permissions.

If a small operation specification remains useful for repeated transport policy, define it once with explicit types and test operation coverage. Do not keep parallel tool-name tables in models, transport, and handlers. Route selection must never accept arbitrary caller URLs.

Keep tool signatures explicit. Share authenticated invocation/error handling only through small helpers that preserve signatures, return annotations, error codes, and audit boundaries. Avoid decorators that hide SDK schema information. Centralize resource and tool error translation while preserving their different MCP error forms.

## 5. Naming, style, and module conventions

- Python files/functions use `snake_case`; classes use `PascalCase`; constants use `UPPER_SNAKE_CASE`. Java retains Sakai's package, class, and method conventions. Shell helper functions retain the `sakai_` prefix.
- Name layers by responsibility (`mcp`, `contracts`, `sakai`, `workflows`) and domain modules by Sakai concepts (`courses`, `announcements`, `assignments`, `grading`). No layer or capability is owned by a Skill. Expand OBO as “on-behalf-of” in module documentation, while retaining the established acronym where it is clear.
- Prefer explicit symbols such as `SubmissionEntry`, `ProposalRecord`, `parse_grading_resource_uri`, `canonical_json_bytes`, and `sha256_hex` over `gm`, `rm`, `parse_uri`, `canonical`, and `digest` at cross-module call sites. Freeze names referenced inside the evaluator until its provenance constraints are addressed.
- Preserve externally visible tool/model names first. Internal renaming must not silently change schema titles, `$defs`, payload fields, or stored JSON.
- Use domain-qualified names when crossing boundaries, such as `NativeGradingContext` versus `GradingContextResult`. Do not rename every local variable merely for consistency.
- Avoid wildcard imports, one-line multi-statement Java methods, and untyped public helpers. Keep external JSON as `Any` only at parsing boundaries; validate before domain use.
- Use keyword arguments for long internal calls. Public MCP arguments remain flattened where the established contract requires them.
- Give each module a short responsibility docstring. Document invariants, native quirks, and reasons for restrictions rather than narrating obvious code.
- Preserve established names with a precise technical meaning, such as `obo.py`, and explain them in the module docstring and README. Renaming or relocating a cohesive component needs a navigation or ownership benefit; consistency alone does not justify rewriting it.
- Avoid catch-all `utils.py`, `common.py`, `helpers.py`, `manager.py`, or `base.py` production modules. A shared function needs a named concern and clear consumers.
- Keep `__init__.py` files small; no wildcard re-exports or import-time app construction. Temporary compatibility imports must have a recorded removal phase.
- Review modules and functions for mixed responsibilities rather than enforcing arbitrary line limits. A file of explicit public definitions, a cohesive contract module, and the frozen evaluator can remain longer without losing their single purpose.
- Adopt Ruff formatting and import ordering incrementally. Enable annotation/type rules for migrated code without a repository-wide suppression flood. Tighten mypy by package once the actual gaps are resolved.

## 6. Native Sakai restructuring

Keep everything inside the existing WebAPI Maven module and `org.sakaiproject.webapi.mcp` namespace. Domain subpackages contain cohesive components, with existing `Mcp` class prefixes retained. Keep grading collaborators together in their domain package so internal checks need not become a wider public API. Verify Spring discovery, filter wiring, qualifiers and test package access when moving classes.

```text
org.sakaiproject.webapi.mcp
  security/             # bearer filter and JWT verification
  courses/              # course, own-grade and legacy metadata reads
  announcements/        # announcement write boundary
  assessment/           # metadata/revision support and setup coordination
  contracts/            # shared wire-contract primitives
  grading/              # focused authorization/evidence/query/file/export/
                        # proposal/mutation/storage components
```

Move small cohesive controllers intact first. Split the grading coordinator along the following existing responsibilities, using descriptive classes and constructor injection:

1. `GradingAuthorization`: acting identity, site visit, assignment equality, group scope, target permissions, and unsupported-feature decisions.
2. `GradingQueryService`: context, roster, paginated submissions, submission detail, assignment listing, and selected grade readback.
3. `GradingFileService`: current submission/assignment files and revision/integrity validation.
4. `GradingExportService`: immutable export capture, export status, captured artifact download, and budgets.
5. `GradingProposalService`: immutable private proposal creation/readback and export ownership/expiry checks.
6. `GradeMutationService`: validate/save/release operations, receipts, reconciliation, and Gradebook synchronization. Keep its mutation boundary coherent; do not immediately create a separate class for each private method.
7. `GradingRecordStore`: existing owner-bound durable storage, lock acquisition, atomic writes, and expiry contract. Separate record kinds only where their actual persistence behavior differs.

Introduce typed DTOs gradually for requests, query results, manifests, and receipts. Preserve Jackson field names, null handling, unknown-field rejection, decimal strings, map ordering where hashed, and stored formats. Do not combine DTO conversion and class extraction in one change. Shared authorization remains explicit at every entrypoint.

Review the custom assignment API/implementation outside WebAPI: `getAssignmentWithGradingEvidence`, `getSubmissionWithGradingEvidence`, the submission version field, row-lock methods, and focused tests. Keep these methods within their existing Sakai modules. Recent fixes load grading evidence inside transactions; class extraction must not reintroduce detached/lazy evidence access or change row-lock lifetimes. Preserve native service calls rather than introducing direct database writes.

Verify Spring proxy behavior before changing method visibility or service boundaries. Self-invocation, constructor wiring, and added `@Transactional` annotations can alter transactions even when method bodies stay unchanged. Keep the original boundary until focused concurrency tests establish equivalence.

## 7. Tests and contract ownership

Retain the useful distinction between unit, protocol, integration, and security tests; group unit tests by production responsibility and then domain where helpful.

```text
tests/
  conftest.py
  fixtures/                         # synthetic builders, not real student data
  unit/
    contracts/                      # setup/grading validation
    workflows/                      # proposal/resource behavior
    grading/                        # evaluator, hashes, reports
    sakai/                          # domain operations, HTTP/retries/integrity
  protocol/                         # real SDK tool/resource envelopes and schemas
  integration/                      # composed app with mocked external HTTP
  security/                         # JWT/OBO/identity isolation and authorization
  contracts/                        # reviewed schemas and deterministic fixtures
```

Before moving code, add behavior coverage where the current suite cannot detect refactor mistakes:

- Record complete `tools/list` and resource-template outputs for every feature-flag combination using synthetic configuration. Compare names, descriptions, hints, input/output schemas, required fields, defaults, aliases, `$defs`, and versions. Sort collection order only where order has no contract significance.
- Capture exact canonical payload hashes, report bytes, URI encodings, and evaluator provenance using fixed synthetic evidence. Compare results against fixtures saved before moves, not values recomputed by the same implementation under test.
- Test the multi-page proposal workflow: consistent snapshots, repeated cursors, incomplete pages, roster cap, unavailable artifacts, integrity conflicts, existing proposal reconciliation, and conflicting proposal IDs.
- Test both SDK `resources/read` and fallback-tool behavior, including MIME metadata, embedded bytes/text, bad URIs, stale revisions, missing principal, disabled feature, expiry, and owner mismatch.
- Exercise transport retry counts and final errors for GET, mutating POST, read-only grade-query POST, malformed JSON, truncated streams, checksum mismatch, and timeouts. Verify failed/uncertain writes are not repeated.
- Verify app lifecycle ownership: close service-owned HTTP clients exactly once and leave injected clients to their caller. If existing app shutdown does not close the client, add that improvement as a distinct tested behavior change after extraction.
- Preserve native positive/negative permission, row-version conflict, unknown/partial commit, feedback preservation, grade release, session isolation, and evidence-loading tests. Add cases for extracted boundaries only where they prove meaningful behavior.

Inject validated request context and gateways through stable construction seams instead of patching implementation-module globals. Pass `httpx.MockTransport`/clients through existing injection points rather than assigning `_http`. Avoid replacing real SDK schema/protocol tests with mocks.

The checked-in JSON contracts, Pydantic/native representations, and public MCP schemas serve different consumers. Document their ownership and add a compatibility check; generate artifacts only where a faithful derivation exists. Do not declare all of them interchangeable or silently regenerate away differences.

## 8. Operations, infrastructure, CI, and documentation

### Operational code

- Keep `./sakai` as the stable human entrypoint. Move login details into a named command implementation using the existing configuration source; remove the duplicated subscription value without changing selection rules.
- Separate the shared Azure configuration/status helpers from SSH/firewall helpers when migrating their callers. Give helpers concern-specific homes such as `scripts/lib/azure.sh` and `scripts/lib/ssh.sh`; preserve standalone command paths during the transition.
- Review `deployment/` bootstrap, repeatable configuration, code release, migration, and scheduled maintenance scripts as distinct responsibilities. Its README already distinguishes several of these; make naming and dependencies agree with it. Move scripts only when that solves a real ownership problem.
- Treat the grading cleanup Python script, systemd unit/timer, and native private-store layout as one compatibility surface. Preserve installed executable paths, locks, expiry, permissions, and retention. Do not relocate them as incidental housekeeping.
- Preserve release/check-only semantics, exact-commit/digest identity, Bash strict mode, quoted arguments, failure behavior, existing rollback, and explicit runtime authorization. Do not make check-only actions allocate resources.
- Keep Bicep entrypoints and existing deployment routes stable. Review parameter names and repeated configuration; extract modules only for independently owned resource groups/responsibilities. Require compiled/deployment-semantic comparison before any proposed Bicep restructuring.

### CI and contributor workflow

- Retain existing Python, shell, Bicep, image, and secret/vulnerability gates. Add format/import checks after formatting migrated code, with an explicit initial exception for the provenance-sensitive evaluator if required.
- Add focused architecture checks for forbidden import directions: transport importing operation/workflow modules, workflows importing MCP presentation/server modules, and production packages importing Skills. Verify all tool registration lives in `mcp/tools.py`. A small AST-based check is sufficient initially; no new framework is required.
- Add a local validation command that invokes the same checks as CI. Keep lint/test/build steps explicit and readable; extract duplicated workflow shell bodies into scripts only when they are actually reused.
- Add focused native MCP checks to the repository workflow using the existing source-validation infrastructure where feasible. First establish the required Java/Maven dependencies and runtime modules; do not claim plain WebAPI-only compilation is enough.
- Make package/server/image version reporting consistent and verify the installed wheel/container imports every new subpackage. Keep source/lock SHA labels and the non-root runtime.
- Avoid unrelated dependency upgrades during this migration. Preserve the pinned SDK and lockfile unless a separately identified change requires otherwise.

### Documentation and Skills

- Update the service README with a short directory map, a “where to change X” table, development commands, and one request trace from MCP handler through gateway/native service to response.
- Update `docs/mcp/architecture.md` for the actual architecture and keep `sakai-adapter.md` as the native route/authentication reference. Link workflow design documents rather than copying their full procedures.
- Resolve contradictory current/historical claims with explicit dated status. Evidence reports remain historical records; do not rewrite an old acceptance result to imply a fresh release.
- Review root/scoped `AGENTS.md`, `docs/MCP_IMPLEMENTATION_RUNBOOK.md`, release guides, contract references, and repository Skill links when paths move. Planning documentation must not mark original runtime acceptance gates complete.
- Keep installed personal Skills separate from repository-owned Skills. Update repository references as needed; installing or modifying a user's personal Skill is a separate explicit action.
- Run `./scripts/check-repo-context.sh` after changing service/deployment layout and inspect links inside existing directories as well.

## 9. Implementation sequence and exit gates

Each phase is one or more focused PRs, not a promise to squeeze a large migration into one review. Every completed PR must run and leave the service functional. Prefer separate formatting, moving, extraction, and behavioral-improvement commits.

| Phase | Concrete work | Required exit evidence |
| --- | --- | --- |
| 0. Freeze the baseline | Record working-tree ownership; capture catalog/schema/golden fixtures; inspect native transaction/wiring tests; create migration checklist | Existing 137 tests/lint/types pass; new characterization cases pass; before-state fixtures are reviewable |
| 1. Establish shared boundaries | Extract errors, safe paths, shared authenticated invocation/error translation; introduce bootstrap wiring and the central `mcp/tools.py` registration entrypoint | Default and opt-in catalogs identical; auth/discovery/health/audit tests pass; temporary imports documented |
| 2. Separate Sakai transport | Extract JSON/binary transport with the same limits, retry rules, and ownership; delegate from existing client temporarily | Existing client tests plus exact retry/stream/error tests pass; fixed origin and OBO isolation preserved |
| 3. Migrate simpler operations | Move all course/announcement/setup/legacy-submission definitions into `mcp/tools.py`; put their native calls in `sakai/`, contracts in `contracts/`, and presentation in `mcp/presenters.py` | Public schema snapshots and current setup/announcement behavior unchanged; definitions remain thin and discoverable together |
| 4. Separate grading contracts/adapters | Move native/public/proposal models; introduce named typed grading operations; update grading callers | Contract/schema compatibility passes; no duplicated operation tables; dispatcher limited to remaining transitional calls |
| 5. Extract grading workflows/resources | Extract orchestration into `workflows/`, pure computation into `grading/`, and SDK presentation into `mcp/`; consolidate remaining grading/proposal/fallback definitions in `mcp/tools.py` | All public definitions live together; proposal/resource protocol tests, deterministic bytes, payload hashes, and evaluator fingerprint match baseline |
| 6. Restructure native integration | Format separately; move small controllers/security; extract authorization/query/file/export/proposal/mutation/storage concerns; then introduce DTOs | Focused native tests and session/transaction/concurrency cases pass; exact routes and durable records remain compatible |
| 7. Align supporting code | Review CLI/shared helpers/deployment maintenance/Bicep; update CI, version metadata, docs, and Skill references | Relevant shell/Bicep/build checks pass; command paths, infrastructure semantics, cleanup storage, guidance, and links remain valid |
| 8. Remove transition code | Delete old facade modules/import shims and string dispatcher after all callers migrate; tighten types/import rules | Search finds no obsolete internal imports or forwarding-only production modules except the deliberate public ASGI entrypoint; full local/CI gates pass |
| 9. Prepare and release when authorized | Package exact commits, release checks, native/MCP compatibility evidence, rollback records, and synthetic acceptance procedure | Separate authorization before runtime changes; native-first rollout if native code changed; accepted live results recorded separately from local success |

Phases 1–5 depend on the Python baseline; phase 6 depends on native baseline and frozen contracts. Supporting documentation moves accompany their owning phase rather than waiting until phase 7. Final cleanup depends on every caller completing migration.

### Check commands for implementation

Run Python checks from `services/mcp/` using the locked environment:

```sh
uv sync --locked
uv run --no-sync pytest -q
uv run --no-sync ruff check src tests
uv run --no-sync mypy src
```

Add `ruff format --check` only after the selected formatting policy and evaluator exception are in place. Add a wheel/install import smoke check during package migration. Run the existing image/security pipeline before considering the service release-ready.

The documented focused Sakai command, from the repository root, is:

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@17 mvn -f apps/sakai/pom.xml -pl webapi -am \
  -Dtest='Mcp*Test,LoginControllerTests' -Dsurefire.failIfNoSpecifiedTests=false test
```

Verify that this selection still discovers tests after package/class moves. Extend it for modified assignment API/implementation tests and concurrency/evidence cases. Record missing local prerequisites rather than treating unrun checks as passes. CI uses its own configured Java path.

Run repository guidance/whitespace checks and Bash syntax/ShellCheck for affected commands. Compile Bicep when templates change. A local build or push does not authorize deployment or starting paused resources.

## 10. Specific migration risks and mitigations

| Risk | Mitigation |
| --- | --- |
| A model/class/signature move changes the MCP schema | Capture generated schemas first; retain public names/aliases; compare actual SDK discovery after every move |
| Cleanup changes evaluator provenance | Freeze the exact function source; compare old/new hash; handle any later engine refactor/version change separately and explicitly |
| Canonical JSON/DTO conversion changes operation hashes or stored receipts | Golden byte/hash fixtures shared across language boundaries; preserve current sorted keys, decimal strings, nulls, and row order |
| Generic retry refactor duplicates a write | Preserve operation semantics and exact attempt counts; include unknown/partial outcome tests |
| New singleton/service state leaks a user or deadlocks limits | Request-scoped identity, no principal on shared clients, scoped semaphore ownership, cancellation/isolation tests |
| Native extraction changes transaction or authorization order | Keep permission calls explicit, preserve lock/service boundaries, run negative-scope and native conflict tests |
| Old exports/proposals become unreadable | Keep record formats/keys/storage paths stable; read baseline synthetic records with the new services |
| New packages work in editable mode but fail in the image | Build/install the wheel, smoke-test imports, then run existing non-editable container build/security checks |
| Broad formatting hides semantic changes | Separate formatting commits; exclude frozen evaluator; review extracted Java methods against their originals |
| Refactor absorbs existing user changes | Record initial status; edit only owned files/hunks; do not reset, stash, overwrite, or commit unrelated work |
| Documentation implies deployed acceptance | Label source, local verification, release identity, and live acceptance separately; preserve dated evidence |

## 11. Completion criteria

The restructuring is complete locally when:

- Every existing Python module and project-owned native MCP class has an explicit destination or a documented reason to remain.
- Useful existing components, including OBO, inbound token verification, configuration, audit, and setup validation, retain clear independent boundaries. Consolidating public tool definitions does not pull these implementations into the tool file.
- Every public tool definition is inspectable in `mcp/tools.py`, including its description, signature, hints, and feature gate. Resource discovery is inspectable in `mcp/resources.py`.
- A contributor can trace from that definition to a named workflow or Sakai operation, its contracts, and its tests using the directory map.
- Adding a grading read no longer requires editing a generic client plus parallel dispatch tables across model and tool files.
- Tool handlers handle protocol concerns; the proposal workflow and deterministic evaluator can run in tests without constructing an MCP server.
- Transport is reusable across Sakai operation modules and has no operation/workflow imports; SDK presentation types stay out of workflow/evaluation logic. Skills remain clients of the API and do not define runtime module boundaries.
- Schemas/catalogs, authenticated behavior, errors, retry counts, canonical hashes, evaluator provenance, and persisted-record compatibility pass their characterization checks.
- Native permission, session, evidence-loading, lock, mutation, and receipt semantics pass focused tests.
- Temporary facades and obsolete imports are removed; the stable ASGI entrypoint remains intentionally supported.
- Formatting, lint, types, architecture checks, appropriate native tests, container/security checks, and repository guidance checks pass without hiding failures behind new blanket ignores.
- Source documentation describes the final layout; existing evidence and live acceptance status remain accurate.

Deployment completion is separate. The root and scoped `AGENTS.md` require explicit authorization for deployment, feature enablement, and runtime state changes. Once implementation and release preparation are ready, present the exact target commits/images, environment, checks, rollback, and expected effects for that authorization. Native changes may require Tomcat build/restart downtime; a Python-only structural release should not require a native release or data migration. Follow the existing release procedures and do not start paused infrastructure implicitly.

## 12. Delivery and later improvements

The local structural migration is implemented and verified as recorded above. Continue through the existing exact-commit release procedure only when release is requested and authorized. Image/security scans require an available Docker daemon. Local source success does not imply deployed/client acceptance.

Later improvements can include typed native DTO conversion, additional workflow capabilities, or a future split of the central tool file if its actual size/ownership warrants it. These should be reviewed as concrete changes rather than added to the structural refactor automatically.

## References

- [Repository strategy](../REPOSITORY_STRATEGY.md)
- [MCP service guidance](../../services/mcp/AGENTS.md) and [README](../../services/mcp/README.md)
- [Sakai source guidance](../../apps/sakai/AGENTS.md)
- [Current MCP architecture](architecture.md) and [native adapter](sakai-adapter.md)
- [Integration guide](../SAKAI_INTEGRATION_GUIDE.md)
- [Assignment setup design](../SAKAI_ASSIGNMENT_SETUP.md)
- [Assignment grading design](../SAKAI_ASSIGNMENT_GRADING.md)
- [Grading resource architecture](../SAKAI_GRADING_MCP_RESOURCES.md)
- [Implementation runbook](../MCP_IMPLEMENTATION_RUNBOOK.md)
- [MCP release guide](../MCP_RELEASES.md), [Sakai release guide](../SAKAI_RELEASES.md), and [grading release order](../GRADING_MCP_RESOURCE_RELEASE.md)
