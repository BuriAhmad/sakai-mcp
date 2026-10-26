# Repository code refactor log

This is the maintained record of code refactors in this repository. The root
[AGENTS.md](../AGENTS.md#record-code-refactors) requires an entry for each future
refactor. Record actual code commits, the reason, before/after, affected areas,
behavior and compatibility impact, verification and release state. Add follow-up
entries rather than erasing history. Do not include credentials, tokens, private
fixture identifiers or user content.

Initial backfill below covers the reviewed authentication work in this chat; it
is not an assertion that all older repository history has been reconstructed.
Worktree boundaries remain governed by [DEVELOPMENT_WORKTREES.md](DEVELOPMENT_WORKTREES.md).

## 2026-10-24 — Consolidate Sakai delegated JWT authentication

- **Branch:** `codex/auth-development`.
- **Code commit:** `8a795a7b32501c130c67c19f0a08d166f8e9cbf1`.
- **Related commits:** `0d20d34d` records the specification/source anchor;
  `f17b7d2b` records implementation verification. The later development release
  selected `2844430a44cf5cf0896ca05c522f7fe4f04c16bd` (includes release tooling).
- **Why:** replace duplicate custom JWT verification with the approved standard
  Spring Resource Server architecture while preserving native Sakai identity,
  session lifecycle and business authorization.

| Before | After |
| --- | --- |
| Legacy McpBearerFilter/McpJwtVerifier and shared DelegatedJwtVerifier | One configured Spring bearer filter/provider/decoder pipeline |
| Custom JWT validation implementations | NimbusJwtDecoder plus the planned Spring validator chain |
| Separate legacy registration | Shared guard before RequestFilter and native binder after it |
| Legacy verifier/filter tests | Useful assertions migrated into consolidated authentication/chain tests |

**Affected areas:** `apps/sakai/mcp-auth/`, WebAPI authentication/streaming wiring,
parent/deploy/module POMs, auth-specific tests, documentation and source-boundary
checks. Removed the superseded production verifier/filter classes and registrations.
No core Sakai, ordinary login, native business service or Python runtime redesign.

**Compatibility:** Framework 5.3.39, Security 5.7.14 and Nimbus 9.37.4 retained;
direct canonical EID resolution and existing feature gates retained. This did not
combine the independent business-API migration line.

**Verification:** focused Java tests (107), Python tests (145), dependency/package
checks and aggregate 455-module build were recorded. Local aggregate completion
used an unchanged-source resume after a browser startup failure. Subsequent
corrected CI passed the full build, 203 browser tests and focused Java tests;
subsequent live read/form/isolation acceptance covered four synthetic principals.

**Release state and limits:** the authorized development release is running at
`2844430a`, with rollback retained. Existing-HTTP/flow reach and historical
attachment acceptance remain outstanding. The pre-existing password API's 500
response for wrong credentials remains documented, although authentication is
rejected and the normal HTML login form works.

Details: [approved plan](mcp/sakai-bearer-auth-refactor-plan.md),
[implementation](mcp/sakai-bearer-auth-refactor-implementation.md),
[release and live acceptance](evidence/mcp/auth-branch-release-2026-10-24.md).

## 2026-10-25 — Align auth implementation with Sakai conventions

Work started during the 24 October review and completed on 25 October (Pakistan
time).

- **Branch:** `codex/auth-development`.
- **Before revision:** `94b2c166` (parent of the cleanup code commit).
- **Code commit:** `7da57f49d92303637c966fe83d4ca60e1fa4971d`.
- **Related documentation/practice commit:** `ade17277` introduces this log,
  the root AGENTS.md requirement and the reviewed source-anchor record.
- **Why:** address the code review's four findings: mixed Mockito versions,
  suppressed internal failure categories, inconsistent XML/POM formatting and
  unnecessarily dense production helpers.

| Before | After | Reason |
| --- | --- | --- |
| Mockito Inline 5.2.0 with managed Core 3.12.4 | Both use `${sakai.mockito.version}`, currently 3.12.4 | Follow Sakai dependency management and remove the mixed test toolchain |
| Internal failures returned sanitized 502/503 with no local failure category | DelegatedDiagnostics logs a fixed enum stage only | Make failures diagnosable without logging request, identity, token, session ID, exception contents or response data |
| Deeply nested anonymous JWKS response/stream wrapper | Named package-private BoundedJwkSetResponse with a small bounded stream | Make ownership, delegation and the existing byte cap easier to inspect |
| Long inline guard predicates and repeated literals | Named internal-dispatch, mixed-credential and flow-header predicates; immutable policy constants | Improve reviewability while retaining predicates and ordering |
| Compressed dependencies, misaligned filter blocks, wildcard production imports and abbreviated headers | Expanded POM entries, locally matched XML indentation, explicit imports, braces and project ECL template headers | Follow surrounding Sakai conventions |

### Affected files/modules

- `apps/sakai/mcp-auth/`: production helpers, guard, response/session/route classes,
  POM and README. Added `BoundedJwkSetResponse.java` and `DelegatedDiagnostics.java`.
- `DelegatedChainTest.java`: its simulated LoggerFactory now provides the new
  diagnostics class logger while retaining all existing denial/session assertions.
- `apps/sakai/webapi/`: POM dependency alignment/formatting and streaming adapter
  header/braces/override annotations.
- Existing auth-only dependency/filter blocks in Announcement, Assignment,
  Content, EntityBroker, Gradebook and Portal POMs/web.xml files: formatting only.
- Root `AGENTS.md` and this document establish the maintained refactor-log practice.

### Behavior and compatibility

The intended functional addition is the fixed-category WARN diagnostic. The
pipeline, claim validators, status decisions, routes, gates, native permission
checks, temporary session lifecycle, response limits and client protocol remain
as before. The named JWKS wrapper retains the same streamed 1 MB limit and
2-second HTTP timeouts. Framework/Security/Nimbus versions and production scopes
are unchanged. No redundant JWT validator/filter was added.

Core/login/business source and all three preserved attachment/access proof files
were compared and remained unchanged. The password API error mapping was not
modified. Existing ordinary login and deployed acceptance findings are preserved.

### Verification

- Focused Maven authentication/login test reactor: **107 tests passed**, zero
  failures, errors or skips (42 shared auth + 65 WebAPI).
- Test runtime reports show **Core 3.12.4 and Inline 3.12.4** in both modules.
- `uv run --no-sync pytest -q tests/security/test_native_auth_boundary.py`:
  **8 passed**.
- Focused Maven package reactor: **BUILD SUCCESS**.
- XML element/attribute/text/order comparison against the before revision:
  unchanged except the intended Inline version expression. This includes the
  servlet filter order and dispatcher mappings.
- Whitespace checks passed. All 14 diagnostic events observed in the focused
  test run ended in an approved enum category.
- Initial Java run found four errors because an existing static LoggerFactory
  mock returned null for the new class-based logger lookup. The fixture was
  corrected and the complete suite rerun; no assertions were removed or relaxed.

Commands (Java 17):

```bash
mvn -B -ntp -f apps/sakai/pom.xml -pl mcp-auth,webapi -am \
  '-Dtest=DelegatedBearerAuthenticationTest,Delegated*Test,PortalContainerTest,ExistingSitesChainTest,Mcp*Test,LoginControllerTests' \
  -Dsurefire.failIfNoSpecifiedTests=false test
mvn -B -ntp -f apps/sakai/pom.xml -pl mcp-auth,webapi -am -DskipTests package
```

### Release state and remaining issues

**Local source cleanup; not deployed.** The running development release remains
`2844430a`. Live results from that release are not relabeled as verification of
this new source commit. Existing-HTTP/flow and attachment limits, the baseline
wrong-password API status issue, and the previously documented SSH release
connection-lifetime limitation remain separate open items. No runtime, Entra,
Azure, data or configuration change was made during this cleanup.

## 2026-10-25 — Make the guarded VM release independent of SSH

- **Branch:** `codex/auth-development`.
- **Code commit:** `c1f6712a0b679bc214fa8629f44bef372857284c`.
- **Before revision:** `fce55272` (same release-launch behavior as deployed `2844430a`).
- **Why:** the previous release's SSH interruption left a completed staged build
  with Tomcat stopped, requiring guarded manual completion. The user authorized
  deployment of the auth cleanup and post-deployment testing.
- **Files:** `scripts/deploy-sakai-release.sh`; procedures in `docs/SAKAI_RELEASES.md`.

| Before | After |
| --- | --- |
| VM release process ran directly on the SSH command's standard streams | The same guarded script runs in a transient systemd oneshot unit with VM-owned journal output |
| Client disconnection could terminate the release process before switching/restart | VM job continues independently; CLI reconnects to monitor unit state |
| SSH completion was the signal to start public health checks | CLI requires successful completed unit plus recorded `healthy` state, then runs the existing public HTTPS check |
| No durable job handle in CLI output | Named unit and journal inspection commands are printed |

The source archive checksum, selected pushed branch, clean-source checks, VM
release lock, 12 GiB preflight, staging, backup, automatic rollback and local
portal checks are retained. The transient unit starts with `--no-block`; the CLI
polls for up to 240 intervals of 15 seconds (connection latency is additional).
Transport errors are retried. Timeout reports that the job may still be running;
it does not start a competing job or declare deployment successful. An explicitly
failed/inactive unit or missing healthy release status fails the command.

**Verification:** Bash syntax and ShellCheck error checks passed. A simulated SSH
monitor exercised success, reconnect, failed unit, inactive unit, bad release
status and timeout; all six expected outcomes passed. The VM reports systemd 255
and permits the required systemd-run command. No Sakai Java, dependency, API,
configuration or database change is included in this commit. Release execution
and live results are recorded separately in
[cleanup release evidence](evidence/mcp/auth-cleanup-release-2026-10-25.md).


## 2026-10-25 — Auth cleanup deployment and verification follow-up

The earlier cleanup entry's "not deployed" state describes its recording time.
The user subsequently authorized release and tests. Cleanup code `7da57f49` and
durable release launcher `c1f6712a` are now included in deployed commit
`0c8767980ce8a9af210d9b41b51c5c1959542451`, release
`20261024T192919Z-0c8767980ce8` from `codex/auth-development`.
Main remains at baseline. The complete VM build and automatic restart/health
checks succeeded without manual recovery, despite a read-only SSH monitor timeout.

CI passed after retrying a Maven artifact-fetch failure. Post-deployment checks
passed 107 Java tests and eight boundary tests. Four-principal live HTTPS checks
passed 89/93 assertions; all four failures are the unchanged upstream wrong-password
API status mapping (500), with anonymous identity verified after rejection. The
actual cleanup helpers, pinned shared dependencies and absence of old verifier/
filter classes were verified in the installed artifacts. See
[the dated release evidence](evidence/mcp/auth-cleanup-release-2026-10-25.md)
for commands, hashes, coverage and remaining acceptance limits. This follow-up
changes documentation only; no login error mapping or attachment proof was changed.


## 2026-10-25 — Make the delegated authentication flow easier to read

- **Branch:** `codex/auth-development`.
- **Code commit:** `d7756ee233affe2a9679e81ff53f2d20611b588d`.
- **Before revision:** `f5693c8b`.
- **Why:** the user requested clearer names, organization and plain-English
  comments after walking through the authentication code.

| Before | After | Reason |
| --- | --- | --- |
| `legacy`, `legacyAllows`, `legacyArtifact` route names | `isCustomMcpEndpoint`, `allowsCustomMcpEndpoint`, `isCustomMcpArtifactRequest` | Say which endpoints are being classified |
| `allows` and `conversationAllows` | `allowsExistingHttpEndpoint` and `allowsToolSessionRequest` | Identify the distinct admission policies |
| JWT callback embedded in `doFilter` | Named `authenticateBearerAndContinue` step | Separate request policy checks from Spring authentication |
| `bind` and `restore` | `executeWithDelegatedSession` and `restorePreviousContext` | Explain the work and its lifecycle |
| `headers`, `bearer`, `account`, `lease`, `delegated`, `beforeThreads` and `guardedResponse` | `authorizationHeaders`, `hasBearerHeader`, `sakaiAccount`, `sessionLease`, `delegatedSession`, `previousThreadValues` and `protectedResponse` | Make local values understandable without tracing their declarations |
| Brief lifecycle comments | Plain-English comments for browser pass-through, route gating, verified identity, session ownership, buffered output and cleanup | Explain why the steps exist |

**Files:** shared auth guard, route policy and session helper; existing
`DelegatedChainTest` call sites for the renamed package-private route method;
module README and this log. Caller searches preceded changes. The three positive
attachment/content proof source files are unchanged.

**Behavior:** method extraction, identifier renaming, comments and documentation
only. Route predicates, their evaluation order, configuration keys/defaults,
error decisions, Spring components, native identity/session handling and response
limits are retained. No servlet mappings, dependencies, native business or core
classes are changed. Ordinary request sessions still close before output is sent;
optional multi-request sessions remain separately gated.

**Verification:** existing focused Java reactor **107 passed** (42 shared auth +
65 WebAPI), zero failures/errors/skips; source-boundary suite **8 passed**. The
three changed production classes retain exactly the same string and character
literal counts/values. Caller searches and final diff review found only the
intended method extraction, names and comments. `git diff --check` passed. No tests
were added and no assertions were weakened. The three proof sources are unchanged.

Commands (Java 17):

```bash
mvn -B -ntp -f apps/sakai/pom.xml -pl mcp-auth,webapi -am \
  '-Dtest=DelegatedBearerAuthenticationTest,Delegated*Test,PortalContainerTest,ExistingSitesChainTest,Mcp*Test,LoginControllerTests' \
  -Dsurefire.failIfNoSpecifiedTests=false test
# From services/mcp:
uv run --no-sync pytest -q tests/security/test_native_auth_boundary.py
```

**Release state:** local source refactor; not deployed. The VM remains at
`0c876798` / `20261024T192919Z-0c8767980ce8`. The existing-HTTP/flow activation
proposal is not being executed, consistent with the user's clarified scope.
