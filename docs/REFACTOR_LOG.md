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
