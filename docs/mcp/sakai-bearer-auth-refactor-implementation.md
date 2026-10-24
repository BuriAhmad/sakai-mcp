# Sakai bearer authentication refactor implementation

Date: 24 October 2026. Worktree: `sakai-mcp-auth-development`, branch
`codex/auth-development`. Starting HEAD: `76fcf7377301c494133ab2c383f570aabe5f5d4c`.
Reviewed implementation source anchor: `8a795a7b32501c130c67c19f0a08d166f8e9cbf1`.
Specification: [approved plan](sakai-bearer-auth-refactor-plan.md).

## Subsequent authorized development release

The user subsequently authorized deployment and resource startup. The auth branch
was deployed as `2844430a` in release `20261024T163517Z-2844430a44cf`.
Builds, installed artifacts, successful real MCP reads, rollback and remaining
acceptance limits are recorded in [release evidence](../evidence/mcp/auth-branch-release-2026-10-24.md).
The deployed environment uses regular username/password login. Read-only checks
found no active SAML configuration; a SAML round trip is not a current acceptance
gate. The implementation-only statements below describe the original implementation
phase; they do not imply that the later authorized release was skipped.

## Implementation

The Sakai-side delegated bearer integration now has **one production JWT
authentication implementation** for both legacy MCP routes and selected existing
HTTP handlers. No Entra, Azure, VM, runtime flag or deployed artifact was changed.

Final request flow:

1. The existing shared `DelegatedCredentialGuard` preserves ordinary no-bearer
   requests and applies explicit credential reach/mixed-credential/transport policy.
2. Standard `SecurityContextHolderFilter(NullSecurityContextRepository)` encloses
   `BearerTokenAuthenticationFilter` → `ProviderManager` (one provider, no fallback
   parent) → `JwtAuthenticationProvider` → `NimbusJwtDecoder`.
3. `DelegatingOAuth2TokenValidator` composes issuer, timestamp, exact tenant/single
   audience/delegated scope, bounded `oid`, singleton identity, required timestamps
   and strict expiration policies. JWT parsing, key/cache/signature processing and
   bearer syntax/extraction belong to Spring. Spring authorities grant no Sakai roles.
4. Only this invocation's authenticated `JwtAuthenticationToken` reaches the native
   adapter: validated EID → `ExternalTrustedEvidence` → native
   `AuthenticationManager`/`UserDirectoryService` → owned native Session and
   `UsageSessionService.login`. Exact EID equality and disabled-user rejection remain.
5. The internal session wrapper selects that Session **before RequestFilter**.
   RequestFilter captures it normally; the existing `DelegatedSessionFilter`
   validates session/UID/EID and aligns native principal/remote-user/current request.
6. Existing business handlers and native permissions execute. Portal/native flow
   ownership, ToolSession/CSRF behavior and bounded leases remain.
7. The guard closes its owned lease and restores native state before emitting
   credential-checked buffered output. Standard Spring cleanup clears the JWT
   context; the guard also clears it on earlier bearer-policy failures.

## Source changes

Paths below are relative to the worktree. The shared Java package is
`apps/sakai/mcp-auth/src/main/java/org/sakaiproject/mcpauth/`.

| Files | Change |
| --- | --- |
| `DelegatedBearerAuthentication.java` | Replaces `DelegatedJwtVerifier` with stock Spring object/validator configuration; header-only resolver projection; sanitized standard challenges; 2-second key HTTP timeouts and 1 MB actual-stream bound |
| `DelegatedCredentialGuard.java` | One shared Spring entry and native adapter; bridge-owned verified identity; separate route gates; audit attributes; robust independent restoration and output withheld on cleanup failure |
| `DelegatedConversations.java` | Only verified-identity type ownership changes; HMAC/limits/flow protocol retained |
| `DelegatedRoutes.java` | Replaces legacy bypass with shared admission; narrow output-policy classification for existing legacy file/artifact GETs |
| `DelegatedResponse.java` | Keeps credential protection; 1 MB ordinary / 10 MiB legacy file cap |
| `apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/WebAppConfiguration.java` | Removes legacy proxy registration/import; preserves guard → RequestFilter → binder |
| `apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/DelegatedStreamingConfiguration.java` | Auth-specific MVC adapter keeps only bound legacy artifact streams synchronous inside the guard; other streams use the original Spring handler |
| `apps/sakai/master/pom.xml`, `apps/sakai/deploy/pom.xml`, `apps/sakai/mcp-auth/pom.xml`, `apps/sakai/webapi/pom.xml` | Managed/shared Resource Server dependencies and explicit WebAPI test dependencies; removes direct production Nimbus ownership from project verifiers |
| Shared verifier/chain/Portal tests; WebAPI Sites/registration/streaming tests | Consolidated real Spring/JWK, native lifecycle, mapping, concurrency and MVC regression coverage |
| `services/mcp/tests/security/test_native_auth_boundary.py` | Admits only planned framework dependencies and proves retired classes/processors/registration are absent; retains no-business/no-advisor and ordering restrictions |
| Module README/AGENTS, worktree/adapter/assignment-setup/integration guides, role metadata | Current implementation and ownership/release boundary |

Deleted production files:

- `apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/McpBearerFilter.java`
- `apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/McpJwtVerifier.java`
- `apps/sakai/mcp-auth/src/main/java/org/sakaiproject/mcpauth/DelegatedJwtVerifier.java`

Deleted redundant test classes: `McpBearerFilterTest`, `McpJwtVerifierTest`, and
`DelegatedJwtVerifierTest`. Their useful success/denial/identity/time/signature/key
failure/audit/cleanup/concurrency cases are retained in the consolidated suites.
`DelegatedSessionFilter` itself needed no source change.

## Dependencies and compatibility

Framework remains **5.3.39**, generic Spring Security **5.7.14**, Nimbus **9.37.4**.
Master manages security-web/oauth2-core/resource-server/jose at the existing
security version; deploy supplies them once alongside core/crypto and Nimbus.
The shared auth JAR uses provided framework dependencies and test-scoped Nimbus
only for synthetic signing fixtures. WebAPI declares the Spring dependencies
explicitly in test scope because provided dependencies do not propagate from the
shared module to caller tests.

Staged dependency trees and copied runtime libraries resolve one version per
artifact. The affected WARs do not embed bearer framework/Nimbus duplicates.
Login retains its SAML 1.0.10.RELEASE and security-config 5.7.14 WAR dependencies;
security-web is now provided by the shared managed dependency path. This shared
classloader packaging change still requires real deployment SAML acceptance.

Configuration retains existing issuer/tenant/audience/scope/JWKS names. Optional
`mcp.integration.identityClaim` defaults to `extn.SakaiEid`; array shape and direct
EID mapping are preserved. No new AID provider/client-ID restriction/clock-skew
property is introduced. Expiration stays strict; nbf retains 60-second leeway.
Legacy routes still require container HTTPS even under native force-secure
settings; existing-handler routes retain RequestFilter's native secure check.

Legacy resource compatibility was characterized against unchanged source:
`McpAssignmentGradingService.FILE_LIMIT` and Python downloads cap each file at
10 MiB; Python ordinary JSON transport caps at 1 MB. The route-specific response
caps match those limits, not the 100 MiB aggregate export budget. The existing
artifact controller's `StreamingResponseBody` is executed synchronously only for
a server-bound artifact request, preserving its authorization and controller.
No async identity propagation or business-controller modification is needed.

## Validation commands and results

All Java commands used `JAVA_HOME=/opt/homebrew/opt/openjdk@17` from the worktree
root. Logs are task-local under `/tmp/sakai-auth-*.log`; synthetic test XML was
preserved under `/tmp/sakai-auth-focused-reports/` before aggregate clean builds.

- `mvn -f apps/sakai/pom.xml -pl mcp-auth,webapi -am -DskipTests compile`: passed.
- `mvn -f apps/sakai/pom.xml -pl mcp-auth,webapi -am clean '-Dtest=DelegatedBearerAuthenticationTest,Delegated*Test,PortalContainerTest,ExistingSitesChainTest,Mcp*Test,LoginControllerTests' -Dsurefire.failIfNoSpecifiedTests=false test`: passed; subsequent tests extended the coverage and the same focused suite was rerun.
- Final focused suite and totals: **107 Java tests passed** (42 shared auth / 65 WebAPI), zero failures/errors/skips..
- Targeted MVC rerun also proves ordinary no-bearer streaming still uses async
  Spring behavior while a delegated legacy artifact remains synchronous.
- `mvn -f apps/sakai/master/pom.xml help:effective-pom -Doutput=/tmp/sakai-auth-effective-master.xml`: passed.
- Reactor and deploy `dependency:tree` filtered to Spring/Security/Nimbus: passed;
  all framework versions above match.
- `mvn -f apps/sakai/deploy/pom.xml dependency:copy-dependencies -DincludeGroupIds=org.springframework.security,org.springframework,com.nimbusds -DoutputDirectory=/tmp/sakai-auth-shared-libs`: passed; inspected staged JAR names.
- A synthetic parent/child URLClassLoader probe with staged runtime JARs and built
  WebAPI/Login classes passed: both children resolve the same SecurityContextHolder,
  bearer filter, JWT provider, decoder and bridge from shared libraries; Login's
  proxy still extends shared Spring Web 5.3.39. This is not a live Tomcat/SAML test.
- `mvn -f apps/sakai/master/pom.xml -DskipTests clean install`: passed; local Maven parent installation only.
- Affected WAR aggregate: `mvn -f apps/sakai/pom.xml -pl mcp-auth,webapi,portal/portal-charon/charon,entitybroker/tool,assignment/tool,announcement/announcement-tool/tool,gradebookng/tool,content/content-tool/tool,login/login-tool/tool -am -DskipTests package`: passed.
- To accelerate inherited UI version-range resolution, checksum-verified public
  WebJar POMs were prefetched from Maven Central into the local Maven cache; no
  dependency constraint/version or repository configuration changed.
- Full aggregate build: completed successfully across the 455-module reactor via an unchanged-source resume. The first `mvn -f apps/sakai/pom.xml -DskipTests clean install` reached module 448, then the existing web-components browser runner exited on a startup timeout/navigation error (197 passing assertions, zero failing assertions, incomplete file startup). One `mvn -f apps/sakai/pom.xml -rf :webcomponents -DskipTests install` retry with the downloaded browser cached passed the remaining eight modules, including **203 browser tests in all 66 files**. No source/test changes or skips were added for the retry. The frontend `npm run test` runs despite Maven's Java `-DskipTests` flag..
- `uv sync --locked`, `uv run --no-sync ruff check .`, `uv run --no-sync mypy src`,
  `uv run --no-sync pytest -q` from `services/mcp`: passed; **145 tests**, type checks
  pass for 17 original runtime files.
- Full `ruff format --check .`: fails on **18 unchanged host files**. The edited
  source-audit test is formatted and lint passes; no unrelated host/evaluator
  formatting was performed to conceal this inherited baseline issue.
- `./scripts/check-repo-context.sh`, POM XML parsing and `git diff --check`: passed.
- Source/preservation and final archive inspection (all rebuilt auth/affected WARs contain no retired verifier/filter classes; bearer framework libraries remain shared): protected source, original business handlers, Python runtime and pinned flow hash match their preserved anchors; 8 source-boundary tests pass. The unmodified worktree verifier passes against the reviewed source anchor; the updated adapter/setup/integration guides and plan/report were explicitly declared as metadata. No business/code preservation restriction was relaxed..

The first attempts exposed and fixed an accidental POM insertion into plugin
metadata, missing explicit caller test dependencies, the HTTP size-test's actual
Spring exception wrapping, and a mock HTTP request whose scheme still implied
HTTPS. Final results above apply to corrected code/tests; no assertion/security
invariant was relaxed to hide these issues.

## Deviations and release gates

The localized WebAPI streaming configuration is the main extension to the initial
file table. It resolves the plan's explicit artifact compatibility gate without
editing the existing controller, native service or core lifecycle. The response
wrapper now emits only after lease cleanup/restoration; a cleanup failure produces
empty 502 and does not leak a partial body or diagnostic.

No `RequestFilter`, native authentication/directory/session/usage/security class,
Login/SAML source, original business handler, Python runtime, public catalog,
contract or evaluator changed. Initial extraction anchors and historical failed
proof evidence stay immutable. The pinned flow helper hash remains
`d5f8d01f58d56be77a06647f09ecf9be00a5188addd0916a80307012eb765aa0`.

Before a separate authorized release:

1. Inventory actual deployed revisions, native providers/overrides, flags and
   shared/WAR classloader origins. No live state was inferred from main or records.
2. Perform the configured real browser/SAML IdP round trip and ordinary session
   regression. Local LoginController/Spring/Portal/MVC tests do not certify live
   SAML authentication or server topology.
3. Review the exact shared JAR/WAR/library set and coordinated restart/rollback
   manifest; source commits and local Maven installation do not deploy.
4. Keep default gates/placement allowlists unchanged until specifically authorized.
   Preserve node affinity and bounded-flow limitations.
5. Attachment positive proofs remain failed/unaccepted; no `/access` reach or
   proof repair was added, and their source/evidence remains unchanged.

This is a local authentication candidate for separate release review. It is not
permission to deploy or a claim that all live acceptance gates have passed.
