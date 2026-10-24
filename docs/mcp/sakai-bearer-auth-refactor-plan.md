# Sakai Bearer Authentication Refactor Plan

Status: approved implementation specification. The original investigation below is
retained as the planning record; see [implementation report](sakai-bearer-auth-refactor-implementation.md)
for the subsequent local implementation, validation results and deviations.
Investigation date: 24 October 2026.
Worktree: /Users/burhanahmadkhan/Desktop/sakai-mcp-auth-development.
Branch: codex/auth-development.
Inspected HEAD: 76fcf7377301c494133ab2c383f570aabe5f5d4c.
Initial Git status: clean (no staged, modified, or untracked files).

This document follows the existing docs/mcp/ convention and the user's explicitly
requested planning scope. All local paths below are relative to this worktree's
root unless a link says otherwise. The supplied request authorizes investigation
and this document, not the proposed code, dependency, configuration, registration,
Entra, deployment, or runtime changes.

## 1. Executive conclusion

Use Spring Security 5.7.14 for bearer extraction and JWT authentication, retaining
the existing shared sakai-mcp-auth JAR as the integration location. Replace both
DelegatedJwtVerifier and McpJwtVerifier with one configuration of
BearerTokenAuthenticationFilter → ProviderManager → JwtAuthenticationProvider →
NimbusJwtDecoder. Do not retain a legacy verifier behind a flag.

Retain and simplify DelegatedCredentialGuard as the shared servlet entry and
Sakai identity/session adapter. Retain DelegatedSessionFilter as a small
post-RequestFilter consistency check and native request-accessor adapter. Retain
the existing bounded conversation and response-credential protection collaborators.
These solve Sakai lifecycle problems which Spring JWT support does not solve.

Select ordering B: Spring authentication and native session selection must occur
BEFORE RequestFilter; the native binder remains AFTER it. The legacy
McpBearerFilter currently swaps only the thread's session after RequestFilter.
That is inadequate as the general reusable implementation: RequestFilter has
already captured another Session in its request wrapper, response processing, and
local variable. Replacing only SessionManager's binding cannot replace those
captured references.

Resolve a validated, single-element extn.SakaiEid array through
ExternalTrustedEvidence → Sakai AuthenticationManager → UserDirectoryService.
Preserve exact resolved-EID equality and tid/oid external identity. No new
AuthenticationIdUDP is justified for the current EID-equals-claim contract.

Remove the separate legacy bearer registration, and admit the existing legacy
route group through the shared implementation under its existing flag. This is
authentication consolidation only; preserve all original business handlers and
catalogs. Generic authentication is reusable independently of /mcp/v1; credential
reach remains explicitly restricted to the currently reviewed servlet/route set.

The design is source-backed, not deployed acceptance. The active server artifact,
runtime provider overrides, and live browser/SAML configuration were not inspected
over SSH. Historical release evidence cannot establish their state today.

## 2. Goals and non-goals

Goals:

- Delegate generic bearer syntax, decoding, JWKS selection/cache, signature,
  issuer, and normal time validation to version-matched Spring components.
- Keep one JWT validation implementation for both currently supported route groups.
- Reuse native account lookup, disabled-account rejection, session lifecycle, realm
  refresh, tool dispatch, and permission checks.
- Preserve the issued-token identity shape, actor binding, explicit credential
  reach, normal browser behavior, and cleanup under exceptions/thread reuse.
- Keep production changes localized to the existing auth module and its wiring.
- Provide concrete source changes and acceptance gates before implementation.

Non-goals:

- No implementation in this task; no changes to Java, POMs, web.xml, flags, Entra,
  Azure, schema, academic records, or deployed artifacts.
- No tool migration, business endpoint addition/removal, new permission advisor,
  global role mapping, or change to ordinary Sakai authorization.
- No Spring/Sakai upgrade, Spring Boot adoption, replacement of SAML, or OBO
  exchange inside Sakai.
- No repair or reinterpretation of recorded attachment proof failures.
- No broad new delegated access to every route or every Sakai WAR.

This worktree preserves original business source as a host. Its auth role explicitly
includes the original WebAPI bearer/JWT files. Future auth test adjustments require
precise preservation-metadata updates; they do not authorize changing business tests
or baseline catalogs to conceal regressions.

## 3. Current architecture

Two generations coexist in this auth checkout.

| Generation | Entry and creation | Authentication and native adaptation | Intended role |
| --- | --- | --- | --- |
| Legacy WebAPI | WebAppConfiguration registers DelegatingFilterProxy targeting the WebMVC component mcpBearerFilter, only /mcp/v1/* inside /api | McpBearerFilter lazily constructs McpJwtVerifier; maps ExternalTrustedEvidence; starts/logs in a temporary session after RequestFilter; invalidates and restores in finally | Original business host and historically released narrow API |
| Shared module | Servlet-created DelegatedCredentialGuard and DelegatedSessionFilter; init obtains services through ComponentManager | Guard lazily constructs DelegatedJwtVerifier; resolves account; selects native session before RequestFilter; binder validates afterward; conversation and response protection apply | Extracted auth development for selected existing handlers |

The shared guard currently bypasses /api/mcp/v1/* through DelegatedRoutes.legacy().
The legacy route therefore still has a completely separate verifier and session
implementation. Both verifier files contain equivalent project-owned Nimbus
processor/key-source and claim-policy logic. Nimbus itself performs cryptography;
the project currently owns its orchestration and verification policy twice.

The original Python host retains services/mcp/src/sakai_mcp/auth.py and obo.py.
The latter exchanges a validated MCP token for a separate Sakai-audience token.
Those are different resource boundaries and are outside this Sakai-side refactor.

### Version and deployment evidence

- apps/sakai/master/pom.xml: Spring Framework 5.3.39; Spring Security 5.7.14;
  Nimbus JOSE/JWT 9.37.4.
- master currently manages spring-security-core, but not the Resource Server/JOSE
  modules required here. Login declares security-web/config at the same security
  version locally.
- apps/sakai/deploy/pom.xml already deploys security-core and Nimbus to the shared
  dependency location. New shared classes cannot rely on Login's WAR-local web JAR.
- No Resource Server/JOSE declaration was found in the relevant current POM path.
- Historical phase-7/phase-21 and grading release records document legacy deployment
  and token observations. The worktree role explicitly does not claim shared-module
  runtime acceptance. This investigation does not assert what is running today.

Relevant records: [worktree ownership](../DEVELOPMENT_WORKTREES.md),
[role](development-lines/role.json), [original adapter](sakai-adapter.md),
[issued-token evidence](../evidence/mcp/phase-6-entra-plan.md),
[historical identity acceptance](../evidence/mcp/phase-21-identity.md).

## 4. Current request lifecycle

### Legacy WebAPI

1. RequestFilter assures/selects a normal native session, stores sakai.session,
   wraps request/response, binds thread state and detects tool context.
2. The WebAPI proxy invokes McpBearerFilter for /api/mcp/v1/*.
3. That filter checks mcp.integration.enabled, request.isSecure(), and its own
   case-sensitive bearer-header syntax; McpJwtVerifier verifies the token.
4. AuthenticationManager authenticates ExternalTrustedEvidence(EID); the filter
   rejects null/blank UID or an EID mismatch.
5. A registered temporary session becomes current and UsageSessionService.login
   sets UID/EID and usage state. External tid/oid become request attributes.
6. The business handler uses native services.
7. Finally invalidates the temporary session and restores the previous session.
8. RequestFilter completes with its originally selected Session and clears native
   thread bindings. The legacy filter does not align all wrapper/tool state.

### Shared existing-handler path

1. Guard recognizes an internal BoundIdentity for a nested tool dispatch, or examines
   top-level credentials. Legacy routes bypass this path.
2. For delegated requests it checks transport, explicit routes, enablement, mixed
   credentials, flow headers, and unsafe session DEBUG logging.
3. DelegatedJwtVerifier validates the token; Sakai resolves trusted account evidence.
4. Guard saves selected native thread bindings/request attributes, clears the
   current ToolSession, opens an isolated session or bounded conversation lease,
   logs in the account, and writes its server-created BoundIdentity marker.
5. NativeSessionRequest supplies an internal cookie for the selected registered
   session, conceals Authorization, and refuses async use.
6. DelegatedResponse encloses native processing so native cookies/session IDs and
   diagnostic bodies cannot escape.
7. RequestFilter sees the internal selected session and captures the correct native
   Session in sakai.session and WrappedRequest.
8. Binder verifies marker/session/UID/EID consistency, aligns remoteUser to EID and
   principal name to UID, and aligns CURRENT_HTTP_REQUEST.
9. Existing native handlers execute. Portal/ActiveTool establish placement/ToolSession.
10. RequestFilter postprocessing completes inside response protection.
11. Guard finishes buffered output, closes the lease, and restores saved bindings
    and request attributes, even on failure.

The guard currently catches downstream IO/servlet/runtime failures and returns an
empty 502 where possible. RequestFilter can itself swallow a downstream exception
when DEBUG is off; tests must characterize that behavior rather than assume every
exception reaches the guard.

## 5. Current custom authentication classes

Prefix A means apps/sakai/mcp-auth/src/main/java/org/sakaiproject/mcpauth/.
Prefix L means apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/.

| Class | Creator/callers | Current responsibility, configuration, state, and coverage |
| --- | --- | --- |
| L/McpBearerFilter.java | WebMVC component scan; WebAppConfiguration proxy; McpBearerFilterTest | Legacy enabled flag, secure transport, manual header extraction; lazy verifier; trusted account resolution; temporary Session/login/finally restoration; tid/oid request attrs |
| L/McpJwtVerifier.java | Legacy filter; McpJwtVerifierTest | Trusted HTTPS JWKS; RS256; issuer/tenant/single audience/scope/time/oid/EID policy; 16,384-character token bound; custom exceptions distinguish credential/key-service failure |
| A/DelegatedCredentialGuard.java | Servlet container registrations; direct test constructors | Header/route/flag/credential checks; lazy shared verifier; native account lookup; thread/attribute snapshot; conversation lease; internal cookie and async wrapper; response lifetime; nested dispatch marker validation |
| A/DelegatedJwtVerifier.java | Guard; verifier tests and mocks in chain/container/Sites tests | Duplicates legacy Nimbus verification and claim policy; owns Identity record consumed by conversations |
| A/DelegatedSessionFilter.java | Same WARs after RequestFilter | Marker/session/UID/EID/dispatch consistency; native remoteUser/principal wrapper; CURRENT_HTTP_REQUEST save/restore; no JWT verification |
| A/DelegatedConversations.java | Guard only | Per-request/session leases; account login; native owner record; HMAC-derived flow Session ID; 64 striped locks; 4 actor/256 node caps; 5-minute lifetime; 60-second inactivity; explicit end cleanup |
| A/DelegatedRoutes.java | Guard; route/dispatch tests | Canonical path/method/query/body/placement credential reach; legacy exclusion; selected grade-submit form boundary; never grants course/resource permission |
| A/DelegatedResponse.java | Guard; DelegatedResponseTest | 1,000,000-byte buffering; session-ID detection in body/headers; suppression of Set-Cookie and X-Sakai-Session; no opaque unchecked compression; finish/reset/error behavior |

No custom endpoint, database, or business service is needed for the target auth.

## 6. Problems with the current design

- Two custom verifier implementations can drift. Two filters maintain different
  header, transport, session, and failure behavior.
- The legacy post-RequestFilter session swap leaves captured request/response
  state associated with another session.
- Broad responsibilities in the guard obscure the separation between JWT
  authentication and Sakai adaptation.
- A bare Spring bearer filter will not clean successful SecurityContext state in
  a finally block. Adding it alone would introduce servlet-thread identity leakage.
- Replacing the verifier with decoder defaults would change accepted token policy:
  issuer alone is insufficient; audience/scope/tenant/identity checks are required;
  stock timestamp validation does not require exp/nbf and uses symmetric leeway.
- Spring's default principal name is sub, whereas existing native accessors use
  EID/UID. Those must not be conflated.
- Simply deleting the guard, flow management, or response wrapper would discard
  necessary native state and credential protections.
- Shared library placement and native OAuth1 filters matter; WebAPI-only Spring
  registration does not cover Direct or Portal.

## 7. Target architecture

    Untrusted HTTP Authorization header
      → Spring DefaultBearerTokenResolver (header-only transport boundary)
      → Spring BearerTokenAuthenticationFilter
      → Spring ProviderManager with exactly one JwtAuthenticationProvider
      → Spring NimbusJwtDecoder + configured OAuth2TokenValidator chain
      → authenticated JwtAuthenticationToken in a fresh Spring SecurityContext
      → existing shared guard's Sakai-specific adapter
      → ExternalTrustedEvidence(validated singleton identity)
      → Sakai AuthenticationManager and UserDirectoryService
      → real native user and isolated native Session
      → normal RequestFilter
      → existing DelegatedSessionFilter validation/alignment
      → existing native controller/service and authorization

A standard SecurityContextHolderFilter with NullSecurityContextRepository encloses
the Spring-authenticated branch and clears it in finally. No Spring authentication
is persisted in a browser HttpSession.

Use the existing guard as the composed servlet entry, avoiding duplicate filter
registrations in every WAR. Refactor/rename the verifier source into a small
DelegatedBearerAuthentication configuration/factory collaborator. That collaborator
constructs stock Spring objects and configured policy predicates; it is NOT a new
JwtDecoder implementation or another verify(rawJwt) abstraction.

Do not install a default full HttpSecurity chain globally. Direct composition of
the two standard Spring filters is sufficient in these manually registered
Servlet applications and avoids unintended login redirects, request caching,
anonymous principals, Spring session persistence, firewall/path changes, or
Spring CSRF rules replacing the native form lifecycle.

## 8. Target request lifecycle

1. Handle a genuine server-created nested dispatch marker using the existing
   strict session/tool/placement checks; do not start a second authentication
   chain or clear the parent Spring context.
2. Ordinary top-level requests without a bearer credential pass directly to the
   native chain. Flow headers without bearer fail as today. Legacy API routes
   retain their flag and mandatory-bearer behavior; cookie-only access does not
   become a way around that requirement.
3. For a top-level bearer attempt, apply explicit credential-reach and transport
   policy before creating native state. Keep per-route enablement independent.
   Delegate bearer syntax/extraction to Spring; reject duplicate/mixed credentials.
4. SecurityContextHolderFilter loads an empty context from NullSecurityContextRepository.
5. BearerTokenAuthenticationFilter invokes ProviderManager → JWT provider → decoder.
   Only successful authentication may invoke the native identity adapter.
6. Adapter requires an authenticated JwtAuthenticationToken from this invocation,
   reads the validated canonical singleton EID plus tid/oid, calls native account
   authentication, and verifies UID and exact EID.
7. Open/register/log in the isolated native session or owner-bound conversation.
   Set marker and internal cookie wrapper; enclose native chain in response guard.
8. Native RequestFilter captures the selected session. Binder verifies/alines native
   state. Existing handlers and permission checks execute.
9. Finish native processing before checking and emitting buffered output.
10. In nested finally blocks, close/invalidate the owned lease as appropriate,
    restore native bindings/attributes, and let Spring clear SecurityContext.
    Failure in one cleanup action must not prevent the others.

No stale/preexisting Spring principal alone can activate the bridge. Fresh
authentication and the invocation's private boundary are required.

## 9. Spring Security components to use

Source/API statements here refer to the 5.7.14 tag, not current 6.x/7.x examples.
The following versioned sources were inspected; links are also implementation
review references.

### BearerTokenAuthenticationFilter

Artifact: spring-security-oauth2-resource-server. Constructors accept either Spring
AuthenticationManager or AuthenticationManagerResolver<HttpServletRequest>.
Select a ProviderManager instance with a JWT provider and no fallback parent.

The filter uses BearerTokenResolver; no token continues the chain. Resolver errors
go directly to the entry point. Successful authentication creates and sets a
SecurityContext. Authentication failures clear it; service failures are rethrown
by the default failure handler. It has no success-path finally cleanup.

Configure NullSecurityContextRepository explicitly and an error policy with no
raw parser/upstream details. Use the stock BearerTokenAuthenticationEntryPoint for
401/challenge formatting; map service unavailability to sanitized 503. Do not
fallback to a cookie, another validator, or an anonymous business request.

[5.7.14 bearer filter source](https://raw.githubusercontent.com/spring-projects/spring-security/5.7.14/oauth2/oauth2-resource-server/src/main/java/org/springframework/security/oauth2/server/resource/web/BearerTokenAuthenticationFilter.java).

### JwtAuthenticationProvider

Artifact: spring-security-oauth2-resource-server. Construct with JwtDecoder.
It invokes decode, then a Converter<Jwt, ? extends AbstractAuthenticationToken>.
Its default JwtAuthenticationConverter produces JwtAuthenticationToken.

BadJwtException becomes InvalidBearerTokenException; other JwtException becomes
AuthenticationServiceException. Keep those categories separate from downstream
Sakai account denial. ProviderManager selects this provider by supports(), with
no SAML/username-password parent.

[5.7.14 provider source](https://raw.githubusercontent.com/spring-projects/spring-security/5.7.14/oauth2/oauth2-resource-server/src/main/java/org/springframework/security/oauth2/server/resource/authentication/JwtAuthenticationProvider.java).

### JwtDecoder / NimbusJwtDecoder

Artifact: spring-security-oauth2-jose. Use
NimbusJwtDecoder.withJwkSetUri(trustedConfiguredUri), explicitly allow RS256 via
SignatureAlgorithm.RS256, supply RestOperations with bounded connection/read
timeouts, build, then setJwtValidator(...).

The builder owns Nimbus processor/JWK-source creation and cache/key selection.
Do not supply a project-created DefaultJWTProcessor or RemoteJWKSet through its
escape hatch. Signature validation precedes returned claims. Its default claim
converter normalizes timestamps; retain custom claim raw shape.

The existing configured JWKS URI avoids startup issuer discovery and any
token-selected URL. Configure issuer validation separately. A resource-server
DSL or JwtDecoders issuer discovery can work, but adds no value for the existing
explicit issuer/JWKS model.

[5.7.14 decoder source](https://raw.githubusercontent.com/spring-projects/spring-security/5.7.14/oauth2/oauth2-jose/src/main/java/org/springframework/security/oauth2/jwt/NimbusJwtDecoder.java).

### JwtAuthenticationToken / SecurityContext

JWT token/converter: Resource Server artifact. SecurityContextHolder and
ProviderManager: spring-security-core. Context lifecycle filter/repository:
spring-security-web.

Read token claims through JwtAuthenticationToken.getToken().getClaims() only
after isAuthenticated() and the fresh-request boundary. Do not coerce the EID
array with getClaimAsString, or treat token.getName()/sub as the Sakai UID.

Use SecurityContextHolderFilter(new NullSecurityContextRepository()), which is
available since 5.7 and clears in finally. SecurityContextPersistenceFilter also
exists but is deprecated in this version; its default HttpSession repository is
wrong here. No inheritable-thread-local strategy or propagation to async work.

[5.7.14 context filter source](https://raw.githubusercontent.com/spring-projects/spring-security/5.7.14/web/src/main/java/org/springframework/security/web/context/SecurityContextHolderFilter.java).

### Validators / converters

OAuth2TokenValidator, DelegatingOAuth2TokenValidator and result/error types are
in spring-security-oauth2-core. JwtIssuerValidator, JwtTimestampValidator and
JwtClaimValidator are in spring-security-oauth2-jose. Set one composed validator
chain on the decoder. Table 11 specifies inherited policy.

Keep JwtAuthenticationConverter, optionally set its granted-authorities converter
to an empty collection. Scope validation belongs in the decoder's validator chain,
not in an authority-to-Sakai-role translation. No custom JWT authentication token
type is needed.

Additional inspected sources:

- [DefaultBearerTokenResolver](https://raw.githubusercontent.com/spring-projects/spring-security/5.7.14/oauth2/oauth2-resource-server/src/main/java/org/springframework/security/oauth2/server/resource/web/DefaultBearerTokenResolver.java)
- [JwtTimestampValidator](https://raw.githubusercontent.com/spring-projects/spring-security/5.7.14/oauth2/oauth2-jose/src/main/java/org/springframework/security/oauth2/jwt/JwtTimestampValidator.java)
- [JwtValidators](https://raw.githubusercontent.com/spring-projects/spring-security/5.7.14/oauth2/oauth2-jose/src/main/java/org/springframework/security/oauth2/jwt/JwtValidators.java)
- [JwtClaimValidator](https://raw.githubusercontent.com/spring-projects/spring-security/5.7.14/oauth2/oauth2-jose/src/main/java/org/springframework/security/oauth2/jwt/JwtClaimValidator.java)
- [DelegatingOAuth2TokenValidator](https://raw.githubusercontent.com/spring-projects/spring-security/5.7.14/oauth2/oauth2-core/src/main/java/org/springframework/security/oauth2/core/DelegatingOAuth2TokenValidator.java)
- [JwtAuthenticationConverter](https://raw.githubusercontent.com/spring-projects/spring-security/5.7.14/oauth2/oauth2-resource-server/src/main/java/org/springframework/security/oauth2/server/resource/authentication/JwtAuthenticationConverter.java)
- [JwtAuthenticationToken](https://raw.githubusercontent.com/spring-projects/spring-security/5.7.14/oauth2/oauth2-resource-server/src/main/java/org/springframework/security/oauth2/server/resource/authentication/JwtAuthenticationToken.java)
- [ProviderManager](https://raw.githubusercontent.com/spring-projects/spring-security/5.7.14/core/src/main/java/org/springframework/security/authentication/ProviderManager.java)
- [OAuth2ResourceServerConfigurer](https://raw.githubusercontent.com/spring-projects/spring-security/5.7.14/config/src/main/java/org/springframework/security/config/annotation/web/configurers/oauth2/server/resource/OAuth2ResourceServerConfigurer.java)

OAuth2ResourceServerConfigurer is in spring-security-config. Its jwt().decoder(...)
and jwtAuthenticationConverter(...) configuration reaches the same JWT provider
and bearer filter. It expects HttpSecurity infrastructure and changes associated
exception/CSRF configuration; it is optional here. Do not add config solely to
construct components which already have public constructors.

### Header-only behavior and a necessary small transport boundary

In 5.7.14 DefaultBearerTokenResolver rejects malformed bearer syntax and permits
non-bearer schemes to continue. Its query/form enable flags default false, but
resolve() still looks at access_token parameters on GET/form POST, and can reject
duplicate parameters or header-plus-parameter combinations before checking the
enable flags. It also reads getHeader(), not every Authorization header.

Consequently, do not call it against every original browser request during an
outer preselection step. Preserve the ordinary no-bearer branch before invoking
the Spring context chain. The existing guard may retain a tiny scheme-presence
check for dispatch selection only; it must not extract token text or parse JWTs.

Use the stock resolver for actual syntax/extraction. Retain duplicate-header and
16,384-character token-size hardening as transport policy. A small resolver
decorator may project a header-only request view (hide access_token only from
the resolver's getParameterValues access), so native business form parsing is
not triggered by generic token extraction. Pass the original request downstream.
Do not silently enable query/body token transport, write another bearer grammar,
or cache raw tokens in native sessions. Tests must pin this version-specific
boundary and non-bearer OAuth1/Basic behavior.

## 10. Required Spring/Maven dependency changes

No dependencies are changed by this document.

| POM | Proposed localized change |
| --- | --- |
| apps/sakai/master/pom.xml | Manage security-web, oauth2-core, oauth2-resource-server, oauth2-jose at existing sakai.spring.security.version=5.7.14 with provided defaults consistent with shared libraries; keep Framework/Nimbus pins |
| apps/sakai/deploy/pom.xml | Add those shared runtime artifacts with compile scope; security-core/Nimbus already supplied. Confirm spring-security-crypto transitive closure and actual deployment plugin output |
| apps/sakai/mcp-auth/pom.xml | Declare resource-server, jose, oauth2-core, core, web and spring-web as runtime compile-time/provided collaborators; remove direct production Nimbus dependency when no production imports remain; keep explicit test-scoped Nimbus for synthetic signing fixtures |
| apps/sakai/webapi/pom.xml | Keep provided sakai-mcp-auth; remove direct Nimbus production declaration once both legacy verifier and its tests move out |
| Existing six native WAR POMs | Keep provided sakai-mcp-auth; no duplicated Resource Server/JOSE payload inside each WAR |
| apps/sakai/pom.xml | Keep existing mcp-auth module; no new auth module required |
| Login POM | Keep SAML and current version configuration. Audit class loading with shared security-web; change dependency scope only if packaging proof establishes a necessary issue and that change is reviewed separately |

Published 5.7.14 POM metadata was inspected directly. Resource Server depends on
security-core/oauth2-core/security-web 5.7.14. JOSE depends on Nimbus 9.22 and
Framework core 5.3.29 by default. Sakai's managed dependencies must keep Nimbus
9.37.4 and Framework 5.3.39 instead; do not downgrade or accidentally introduce
multiple versions. The existing root pin is a compatibility decision, not a reason
to retain custom Nimbus verification.

Metadata references:
[Resource Server POM](https://repo.maven.apache.org/maven2/org/springframework/security/spring-security-oauth2-resource-server/5.7.14/spring-security-oauth2-resource-server-5.7.14.pom),
[JOSE POM](https://repo.maven.apache.org/maven2/org/springframework/security/spring-security-oauth2-jose/5.7.14/spring-security-oauth2-jose-5.7.14.pom),
[OAuth2 Core POM](https://repo.maven.apache.org/maven2/org/springframework/security/spring-security-oauth2-core/5.7.14/spring-security-oauth2-core-5.7.14.pom).

The shared JAR and these runtime libraries must be packaged/deployed consistently;
a WebAPI-only WAR change is insufficient for the shared servlet registrations.
Per-filter immutable Spring object graphs are acceptable: one implementation does
not require a global mutable decoder singleton across every WAR. Lifecycle,
configuration generation and JWK cache ownership must be explicit.

## 11. Entra/JWT configuration model

Use ServerConfigurationService and the existing mcp.integration.* namespace.
Retain deployed property names for issuer/tenant/audience/scope/jwksUri; introducing
a second oauth.* configuration copy would defeat consolidation. Separate generic
token settings from native session settings in code/configuration documentation.

| Setting/policy | Current evidence | Target decision |
| --- | --- | --- |
| mcp.integration.enabled | Legacy API disabled by default | Preserve as legacy route admission gate, not validator selector |
| mcp.integration.existingHttp.enabled | Shared existing-handler gate default false | Preserve independently; both gates use the same Spring pipeline |
| issuer / tenant | Exact configured iss and tid | JwtIssuerValidator plus configured tid claim validator; no common/multi-tenant issuer or token-derived discovery |
| audience | Exactly one expected Sakai resource audience | JwtClaimValidator checking singleton normalized audience equality; reject MCP/Graph/extra audiences |
| jwksUri / algorithm | Trusted HTTPS setting; RS256 | Spring builder with explicit RS256 and trusted HTTPS URI validation; no jku/x5u-driven lookup |
| scope | Exact member in space-delimited scp | Require string scp with configured delegated scope; roles-only/app-only tokens fail |
| exp / nbf | Both required; exp strictly after now; nbf at most 60 seconds ahead | Compose stock JwtTimestampValidator(60 seconds) with required-claim predicates and strict-exp predicate using injected Clock; avoid silently broadening expiration acceptance |
| identityClaim (proposed new property) | Java currently hard-codes extn.SakaiEid; Python has its own configured downstream claim | Default extn.SakaiEid; validated raw value must remain singleton list of a bounded nonblank, trimmed, control-free string |
| oid / tid | External audit and flow ownership identity | Require bounded canonical oid and exact configured tid; retain independently of Sakai EID |
| permittedClientIds (optional future policy) | Neither current Java verifier enforces azp/appid | Do not enable by default; only add with a concrete requirement and verified token-version contract |
| clockSkewSeconds (optional new setting) | nbf uses fixed 60, expiration uses zero leeway | Default 60 for stock time window; strict exp remains explicit. Any change needs policy review/tests |
| conversations.enabled / flowSecret / placements | Native session protocol | Preserve separate native/session settings and disabled defaults; no generic JWT concern |

The extra expiration predicate preserves the inherited asymmetric policy using
Spring's validator interface; it does not recreate a token parser, key client, or
JWT processing engine. Stock timestamp validation permits absent exp/nbf, so
explicit presence predicates are required as well. Use deterministic Clock in
tests, including exact boundary instants. If a later decision chooses symmetric
leeway instead, record that changed acceptance policy before implementation.

For OBO, the downstream token's audience/scope and stable user/tenant claims are
required; Sakai has neither the original MCP token nor OBO credentials. Sakai
cannot independently compare two tokens' oid values. Python performs that
comparison at its boundary. Do not require azp to equal the AI front-end client;
an OBO downstream caller may instead identify the middle tier. Optional client
restriction would use the reviewed version-appropriate azp/appid, not guess
between them, and never replace delegated scope or native authorization.

Microsoft references:
[OBO flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow),
[claims validation](https://learn.microsoft.com/en-us/entra/identity-platform/claims-validation).
No tenant/app values or secrets need to appear in this plan.

## 12. Sakai components to reuse

### RequestFilter

Source: apps/sakai/kernel/api/src/main/java/org/sakaiproject/util/RequestFilter.java.
It is servlet-created and obtains native services through ComponentManager.
Key locations: doFilter around line 365; assureSession around 1125;
WrappedRequest around 1548.

It handles encoding/uploads, chooses a native Session from principal/allowed
session parameter/cookie, stores ATTR_SESSION, binds SessionManager, detects tool
placement, wraps request/response, and postprocesses using the locally captured
Session. Nested ATTR_FILTERED requests avoid outer session selection but still
set request/response thread references. Outer finally clears ThreadLocalManager.

Reuse unchanged. Setting the native current session before it runs is insufficient
on its own: assureSession must select the same registered session. The existing
internal cookie wrapper provides that without modifying core Sakai.

### ExternalTrustedEvidence

Utility class at kernel/api/.../util/ExternalTrustedEvidence.java implements
user.api.ExternalTrustedEvidence. It merely carries an identifier. It performs
no JWT authentication. Construct it only after Spring success and identity-shape
validation.

### AuthenticationManager

kernel/kernel-impl/src/main/webapp/WEB-INF/user-components.xml declares the
org.sakaiproject.user.api.AuthenticationManager bean as UserAuthnComponent, with
lookup-method injection for UserDirectoryService and AuthenticationCache.

UserAuthnComponent.authenticate handles ExternalTrustedEvidence by calling
getUserByAid, rejecting the exact disabled property value "true", and returning
org.sakaiproject.util.Authentication(native UID, EID). Unknown users become
AuthenticationMissingException. This external path does not reuse the password
authentication cache. It also does not apply the password path's IP whitelist;
document that actual behavior rather than assume password policy parity.

### UserDirectoryService

The same XML declares PrecachingDbUserService → DbUserService →
BaseUserDirectoryService, with storage/provider and session/security collaborators
injected via lookup methods. getUserByAid uses the configured provider when it
implements AuthenticationIdUDP and resolves an EID/UID; otherwise it falls back
to getUserByEid(aid). getCurrentUser derives its UID from SessionManager and falls
back to anonymous if missing. No Spring Security lookup is involved.

### AuthenticationIdUDP

Interface: kernel/api/.../user/api/AuthenticationIdUDP.java; method spelling is
getUserbyAid(String, UserEdit). BaseUserDirectoryService.getUserByAid around 1348
uses it if the active provider supports it; otherwise/failure uses EID fallback.

Repository examples include federating FilterUserDirectoryProvider and
UnboundidDirectoryProvider. The default providers/component/.../components.xml
contains commented provider examples, not proof of an active production mapping.
Runtime overrides can replace that bean. No new mapper is proposed.

### SessionManager

tool-components.xml supplies SessionComponent, backed by native ThreadLocalManager
and registered Session storage. startSession registers a native MySession.
setCurrentSession changes only the thread binding. getCurrentSession can create an
unregistered anonymous session as a side effect; getCurrentSessionUserId reads the
bound UID directly. Snapshot raw existing bindings before getters manufacture
state. ToolSession is a separate binding.

### UsageSessionService

event-components.xml supplies UsageSessionServiceAdaptor with session, authz,
event, storage and other native collaborators. login(uid,eid,...) starts/reuses
usage state, writes Session UID/EID, refreshes externally provided realms subject
to the native refresh cache, sets JUST_LOGGED_IN, and posts a login event.

This is why directly setting userId/userEid is not the supported replacement.
Temporary session login/invalidation can have usage/event/database effects even
without business writes; include those costs in acceptance.

### ThreadLocalManager, SecurityService and ToolManager

util-components.xml declares ThreadLocalComponent. set(null) removes a binding;
clear invokes ThreadBound unbind callbacks then clears its map. This is separate
from Spring SecurityContextHolder and does not clear Spring automatically.

authz-components.xml supplies native security wiring. SakaiSecurity.unlock uses
UserDirectoryService.getCurrentUser/native UID, checks native realms and optional
native advisors. Do not add an advisor or map SCOPE_ authorities to Sakai roles.

ActiveToolComponent and Portal ToolHandler bind placement/current tool/ToolSession,
dispatch to a named servlet, and restore prior tool context. The auth adapter
must preserve that lifecycle. It must not manufacture a placement merely because
an HTTP caller supplied an identifier.

## 13. Spring-authenticated principal → Sakai identity bridge

Minimum custom bridge responsibilities:

1. Require the current invocation's successful authenticated JwtAuthenticationToken.
2. Extract already validated singleton EID and bounded tid/oid.
3. Authenticate ExternalTrustedEvidence through the native manager.
4. Require real UID and exact resolved EID under the current direct-EID contract.
5. Open the owned native session/flow lease and install the internal selection
   wrapper/marker.
6. Execute the unchanged native chain within credential protection.
7. Close the owned lease and restore native state in finally.
8. After RequestFilter, validate captured native state and align accessors.

Keep two lifecycle filters because these responsibilities straddle RequestFilter.
Keep conversations and response protection separate because they have distinct
lifetime/streaming responsibilities and substantial existing tests. One giant
"minimal" class would be harder to verify.

Move the small ExternalIdentity(EID, tenant, object) record out of the removed
verifier into the bridge. Conversations consumes that verified record; it never
reads JWTs or HTTP identity headers.

The configuration collaborator owns only construction of Spring components,
validators and small transport/error policies. It should expose a standard Filter
graph or configuration, not verify(rawToken), JWK, or claims-parser methods.

## 14. Sakai session/current-user lifecycle

An isolated registered native session is necessary for the current supported
multi-WAR/native-UI use. Spring SecurityContext alone cannot satisfy
AbstractSakaiApiController.checkSakaiSession, BaseUserDirectoryService.getCurrentUser,
SakaiSecurity, AssignmentServiceImpl current-user checks, or native tool state.

Using the existing browser Session and temporarily changing its user fields would
corrupt session-owned state and can affect concurrent browser requests. An
unregistered thread-only Session cannot reliably be selected by RequestFilter or
retained across flow requests. Preserve startSession + login + owned invalidation.

Keep two lifetimes:

- Stateless native read: fresh registered native session per request, invalidated
  after native postprocessing.
- Explicit conversation: bounded registered session reused only for the same
  verified tenant/object/UID/EID and nonce; validate account afresh each request;
  close at explicit end/expiry. JWTs and Spring contexts are never retained there.

Preserve saved session/tool/request/response/context/server URL/portal-path
bindings and the current request attributes. Invalidation must run with the owned
session current; MySession.destroy clears bound attributes and storage and removes
its current binding. Restore previous values even if invalidation fails.

Existing restored-key lists are not proof that every native cache is safe to
restore after RequestFilter.clear(). Audit identity-dependent caches, native
security advisors and any ThreadBound entries in the real chain. Do not copy an
entire arbitrary thread map or restore stale permission caches blindly.

Maintain the internal cookie wrapper and the response envelope through
RequestFilter's output-cookie phase. Binder still aligns remoteUser=EID,
principal.name=UID, and CURRENT_HTTP_REQUEST; a Spring JWT subject cannot stand in
for any of these native values. Preserve RequestFilter's own HTTP-session/context
semantics rather than synthesizing a universal getSession() override.

Portal/ActiveTool and native forms retain their ToolSession/CSRF state. Authentication
does not waive CSRF, site/placement relationships, business validation, or roles.

## 15. Selected filter ordering and justification

| Candidate | Native consequences | Decision |
| --- | --- | --- |
| A: RequestFilter → Spring → current-session swap | ATTR_SESSION, WrappedRequest.m_session, response/session postprocessing and detected ToolSession can still refer to the first session. Direct principal selection has already run. Fixing this requires replacing more native behavior | Reject as the general shared architecture |
| B: Spring → resolve/select native session → RequestFilter → binder | RequestFilter captures the actual delegated native Session from the outset; its ordinary wrappers and cleanup can be reused | Select; retain small before/after collaborators |

Evidence: RequestFilter.assureSession writes sakai.session and calls
setCurrentSession. doFilter retains local Session s across downstream handling and
postProcessResponse/cookie handling. WrappedRequest stores m_session and uses it
in getRemoteUser/getSession. setCurrentSession changes none of those references.

The guard's pre-RequestFilter internal request hides Spring/container principal
and remote user during native selection. Direct's sakai.session.auth=basic otherwise
derives a session from principal via makeSessionId. Binder exposes native accessors
only after selection. Do not add SecurityContextHolderAwareRequestFilter before
RequestFilter, because its Spring principal wrapper would change that selection.

The Spring context lifecycle encloses the native lifecycle. Genuine nested
Portal dispatch keeps the same authenticated parent invocation; target-WAR guard
validates the private marker/session/placement and does not reauthenticate. A
public HTTP request cannot set Java request attributes. Still reject unexpected
ERROR/ASYNC dispatch and forged or inconsistent internal markers.

## 16. Normal browser/session behavior

No-bearer normal requests must keep their original request/response, session,
principal, parameters, encoding, cookie and Spring context behavior. Avoid eager
decoder creation or network calls on that branch. No-Bearer anonymous requests
remain subject only to normal Sakai behavior.

Ordinary Basic and OAuth1 traffic remain native mechanisms; bearer auth does not
override them. For a top-level delegated attempt, mixed cookies, preexisting
container identity, session parameters/headers or OAuth1 credentials must fail
before native delegated state is created. Do not silently prefer one actor.

Legacy API routes are a deliberate existing exception to anonymous pass-through:
they remain flag-gated and bearer-required. "No bearer leaves normal behavior
unchanged" must not expose protected /mcp/v1 handlers anonymously.

Malformed/invalid bearer requests stop at authentication. Authentication success
followed by native mapping failure stops with sanitized 403. Native permissions
then determine actual business access. Challenge/error behavior must not redirect
an API call into the browser login page.

## 17. SAML boundary and why it remains unchanged

Login's web.xml maps SafeDelegatingFilterProxy named springSecurityFilterChain to
/container/* inside the login WAR, on REQUEST/FORWARD/INCLUDE. The proxy deliberately
becomes a no-op when its optional Spring bean/context is absent.

xlogin-context.saml.xml configures the Spring security chain, SAMLProcessingFilter,
SAMLAuthenticationProvider and success/failure handlers. Browser SAML authentication
surfaces a remote user through that machinery; ContainerLogin uses
ExternalTrustedEvidence(remoteUser), native AuthenticationManager and
UsageSessionService.login(EVENT_LOGIN_CONTAINER).

That native trusted-evidence convergence is reusable. The SAML message decoder,
redirects, SAML provider, metadata and browser security-context persistence are
not bearer JWT infrastructure. Do not reuse the safe no-op proxy for required
enabled bearer security: a missing bearer chain must fail closed, not disappear.

Inspecting these templates establishes source boundaries only. It does not prove
SAML is enabled or which login override is active on the current server.

## 18. Servlet-context / WAR registration strategy

The following is the actual inspected registration inventory. R/F/I means
REQUEST/FORWARD/INCLUDE. Context names are the intended deployment names; verify
the runtime inventory before release. All XML paths end in src/webapp/WEB-INF/web.xml.

| WAR/module | Context / target | Current mapping and order | Context creation / target |
| --- | --- | --- | --- |
| webapi | /api; all URLs | guard R /* → RequestFilter R/F/I /* → binder R /* → legacy proxy R /mcp/v1/* | WebAppConfiguration Java initializer; AnnotationConfigWebApplicationContext(WebMvcConfiguration); Sakai parent via SakaiContextLoaderListener; component mcpBearerFilter |
| entitybroker/tool | /direct; sakai.entitybroker.direct | guard R → oauth.pre R → RequestFilter R/F/I → oauth.post R → binder R | Servlet-created filters; ComponentManager services; existing Direct servlet and native OAuth1 |
| portal/portal-charon/charon | /portal; sakai.portal.charon | guard R → RequestFilter R/F/I → binder R | Servlet-created filters; SakaiContextLoaderListener; Portal native dispatch |
| assignment/tool | /sakai-assignment-tool; sakai.assignment.grades | guard R/F/I → RequestFilter R/F/I → binder R/F/I | Servlet-created filters; native tool context. Separate sakai.assignment has RequestFilter only |
| announcement/announcement-tool/tool | /sakai-announcement-tool; sakai.announcements | guard R/F/I → RequestFilter R/F/I → binder R/F/I | Servlet-created filters; synoptic servlet has RequestFilter only |
| gradebookng/tool | /sakai-gradebookng-tool; sakai.gradebookng | guard R/F/I → RequestFilter R/F/I → binder R/F/I; static cache mappings separate | Servlet-created filters; Wicket/native context preserved |
| content/content-tool/tool | /sakai-content-tool; sakai.filepicker | guard R/F/I → RequestFilter R/F/I → binder R/F/I | Servlet-created filters; resources/dropbox/resource helper have RequestFilter only |
| login/login-tool/tool | /sakai-login-tool; /container/* | Spring SAML proxy URL mapping plus native login RequestFilter mappings | Optional WAR Spring SAML context; keep separate |
| access/access-tool and other WARs | /access and others | No shared delegated capability accepted by these registrations | Do not add a registration to repair attachment reach during this refactor |

Target: keep existing guard/binder names and XML registration order. Their internal
implementation changes; no extra generic Spring filter is copied into each WAR's
XML. In WebAPI, delete the legacy proxy registration/import and bean; the existing
guard becomes the sole authentication entry for both route groups.

Factory initialization uses the existing servlet lifecycle/ComponentManager
pattern, calling native services by their types/bean IDs. It builds immutable
standard Spring collaborators per entry instance and destroys owned resources
on filter shutdown. This avoids adding Spring Boot or a new context-loader
requirement to Direct/native tool WARs. The library is shared; each WAR registration
is explicit. A /* mapping in WebAPI covers only that WAR.

Preserve exact credential reach in DelegatedRoutes; removing legacy() bypass means
adding explicit legacy admission under mcp.integration.enabled, including mandatory
auth when no bearer exists. Existing-handler reach keeps its independent gate.
Do not generalize to all routes just because the JWT capability is reusable.

Direct OAuth1 remains in its existing order. Hiding Authorization prevents bearer
misinterpretation, but OAuthHttpServiceImpl also examines oauth_token parameters.
Add mixed-protocol negatives for query/form OAuth1 tokens; do not let its
pushAdvisor path execute during a delegated bearer request. Modify the project
boundary if necessary, not upstream OAuth filters.

## 19. Identity claim/AID/EID strategy

The current Java claim name is hard-coded extn.SakaiEid, whose observed issued-token
representation is a singleton array, not a scalar. Existing Python configuration
does not make the Java name configurable automatically.

Preserve:

    validated {"extn.SakaiEid": ["27100405"]}
      → exact "27100405"
      → ExternalTrustedEvidence("27100405")
      → UserDirectoryService.getUserByAid
      → getUserByEid fallback
      → native UID and EID
      → require returned EID == "27100405"

The example is illustrative, not a discovered user record. Reject missing/scalar/
multi-value/non-string/blank/padded/control-character/overlong identity. Do not
strip, infer, auto-provision, or fall back to UPN/email/oid.

Case B, where the AID intentionally differs from EID, would require a canonical
provider mapping through AuthenticationIdUDP and a reviewed change to the current
exact-EID invariant. It is not part of this refactor. Provider fallback also means
runtime mapping behavior must be confirmed rather than inferred from an interface.

Keep tid+oid as external identity for audit/flow ownership, separate from native
UID/EID. Preserve legacy mcp.externalTenantId/mcp.externalObjectId attributes with
save/restore semantics; current source references them only in the legacy filter
and its tests, but silently losing them is unnecessary compatibility risk.

## 20. Exact current files to modify

The following is the proposed file-by-file implementation scope. This document
does not perform these edits. A and L are the full production prefixes in section
5. T is apps/sakai/mcp-auth/src/test/java/org/sakaiproject/mcpauth/.

| Existing file/class | Current responsibility | Target responsibility / action | Dependencies/callers affected | Tests affected |
| --- | --- | --- | --- | --- |
| A/DelegatedCredentialGuard.java | Combined custom header/JWT/native lifecycle | MODIFY/SIMPLIFY: compose stock Spring chain; retain native mapping/session/transport/reach/response lifetime only | Servlet registrations, conversations, binder, test constructors | DelegatedChainTest, PortalContainerTest, ExistingSitesChainTest |
| A/DelegatedJwtVerifier.java | Custom Nimbus processing and Identity | RENAME/REPLACE with DelegatedBearerAuthentication.java: only stock component configuration, predicates, narrow transport/error policy; no verify method | Guard, conversations record type, mocks | Rename/rewrite DelegatedJwtVerifierTest as Spring pipeline/configuration tests |
| A/DelegatedSessionFilter.java | Native state validation/accessor alignment | KEEP with small MODIFY only for consolidated marker types/legacy reach; no JWT work | Guard marker, native request thread accessor | Shared chain/container tests |
| A/DelegatedConversations.java | Session/flow lifecycle; verifier Identity type | MODIFY type reference to bridge ExternalIdentity; preserve owner/HMAC/lease/limits behavior | Guard | Flow, expiry, account-change, concurrency tests |
| A/DelegatedRoutes.java | Reach policy and legacy bypass | MODIFY: remove bypass; admit explicit legacy route group under existing gate; preserve existing route/placement constraints | Guard, source audit | Reach/gate/mandatory-bearer/dispatch tests |
| A/DelegatedResponse.java | Credential suppression and bounded output | KEEP behavior; legacy now uses same envelope | Guard | Existing response tests plus legacy envelope regression |
| L/McpBearerFilter.java | Legacy independent authentication/session filter | DELETE after shared chain takes over in same code transition | WebAPI component scan and proxy | Migrate native lifecycle cases to shared chain |
| L/McpJwtVerifier.java | Duplicate custom token verifier | DELETE | Legacy filter/test and WebAPI Nimbus dependency | Merge meaningful cryptographic negatives into one shared suite |
| apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/WebAppConfiguration.java | Dual entry wiring | MODIFY: remove mcpBearerFilter proxy registration and stale order comment; retain guard → RequestFilter → binder | WebMVC component discovery | Add actual initializer registration test |
| apps/sakai/master/pom.xml | Managed versions/shared defaults | MODIFY metadata as section 10 | All selected modules | Dependency/version assertions |
| apps/sakai/deploy/pom.xml | Shared runtime artifacts | MODIFY shared security artifact list | Native shared runtime/classloader | Staged dependency/package audit |
| apps/sakai/mcp-auth/pom.xml | Auth module dependencies | MODIFY to Spring Resource Server; move signing Nimbus to test scope | Shared JAR/runtime closure | Module dependency-boundary audit |
| apps/sakai/webapi/pom.xml | Legacy direct Nimbus + provided auth | SIMPLIFY direct verifier dependency | WebAPI tests | Package/compile and existing business tests |
| T/DelegatedJwtVerifierTest.java | Verifier fixture/token negatives | RENAME/MODIFY to DelegatedBearerAuthenticationTest.java; exercise real decoder/provider/filter with synthetic keys | Standard Spring graph | One final JWT validation suite |
| T/DelegatedChainTest.java | Mock verifier + native RequestFilter chain | MODIFY injection/fixtures; test actual Spring boundary and native bindings | Guard/binder graph | All existing invariants; new Spring cleanup tests |
| T/PortalContainerTest.java | Actual Tomcat/Portal forward to synthetic target | MODIFY authentication injection; keep native dispatch fixture | Shared classes across contexts | Parent/nested Spring context lifetime |
| apps/sakai/webapi/src/test/java/org/sakaiproject/mcpauth/ExistingSitesChainTest.java | Existing Sites/RequestFilter characterization | MODIFY injection to consolidated standard authentication | Guard and actual Sites controller | Account and native authorization regression |
| apps/sakai/webapi/src/test/java/org/sakaiproject/webapi/mcp/McpBearerFilterTest.java | Legacy-only session tests | MOVE/MERGE scenarios to shared Spring/native suite, then DELETE old class | Existing legacy route regression | Preserve success, failure, flags, concurrency and audit attrs |
| apps/sakai/webapi/src/test/java/org/sakaiproject/webapi/mcp/McpJwtVerifierTest.java | Duplicate verifier suite | MERGE distinct cases into shared suite, then DELETE | Synthetic signing fixtures | Preserve key failure classification and identity shapes |
| services/mcp/tests/security/test_native_auth_boundary.py | Native ownership/dependency/registration source audit | MODIFY only declared Spring auth dependencies and single-path assertions; preserve no-business/no-advisor constraints | No Python runtime change | Explicit single verifier and registration absence checks |
| apps/sakai/mcp-auth/README.md | Current implementation documentation | MODIFY after implementation to actual Spring composition, properties, tests and remaining limitations | Maintainers | Documentation/source checks |
| apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/README.md | Host implementation/source guidance | MODIFY auth pointer only; business source remains frozen | Maintainers | Preservation review |
| docs/mcp/sakai-adapter.md | Legacy lifecycle/configuration guide | MODIFY to consolidated ordering and compatibility effects | Operators | Documentation review |
| docs/mcp/development-lines/role.json and verify_arrangement.py | Ownership/source-anchor checks | MODIFY narrowly for reviewed auth test paths/new plan metadata and actual code anchor; keep immutable extraction anchor and business protection | Auth worktree source audit | Verifier cannot keep an outdated blanket test-path restriction |
| docs/DEVELOPMENT_WORKTREES.md and apps/sakai/AGENTS.md / mcp-auth/AGENTS.md | Ownership entrypoints | MODIFY only obsolete auth file/path/wiring descriptions if needed | Maintainers | Repository guidance review |
| deployment/configure-mcp-sakai.sh | Original property block generator | KEEP existing issuer/tenant/audience/scope/JWKS/gate interface; MODIFY only if adding optional identity/skew settings to supported interface | Future release preparation only | Shell/metadata checks; do not apply to VM |

Do not add a second module or a NewSpringJwtVerifier beside the old ones. Source
prefixes in this table expand to concrete paths; no business controller/service
is included.

Existing XML registrations and six WAR dependency declarations can remain unchanged
with the selected in-place composition. If an implementation renames a servlet
entry class, list and update each explicit registration from section 18; this plan
prefers retaining names to avoid that churn.

## 21. Exact current files/classes to delete or retire

One coordinated implementation transition must remove:

- apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/McpBearerFilter.java.
- apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/McpJwtVerifier.java.
- The mcpBearerFilter bean/qualifier references and sakai.mcp.bearer proxy registration.
- DelegatedJwtVerifier as a verifier/class name and all project-owned
  DefaultJWTProcessor/RemoteJWKSet/JWSVerificationKeySelector/processor.process
  production usage for this integration.
- Old verifier exception classes and verifier-owned Identity coupling.
- Duplicate legacy test classes after their distinct assertions are transferred.

Retire the shared guard's custom substring/regex token extraction and direct
verify() calls. Small size/multi-header/scheme-selection policy is not a JWT
implementation and must delegate actual extraction to Spring.

Do NOT delete DelegatedResponse, the conversation HMAC, route restriction, native
binder, or historical evidence merely to reduce a security-code line count.
Conversation HMAC establishes opaque native session ownership, not JWT signatures.

## 22. Existing files that remain unchanged

Preserve upstream RequestFilter, UserAuthnComponent, ExternalTrustedEvidence,
BaseUserDirectoryService/PrecachingDbUserService, AuthenticationIdUDP,
SessionComponent/MySession, UsageSessionServiceAdaptor, ThreadLocalComponent,
SakaiSecurity, ToolHandler and ActiveToolComponent.

Preserve native business code under WebAPI MCP controllers/services, Assignment,
Announcement, Gradebook, content, site, storage and schema. Preserve public
catalogs/contracts/evaluator bytes.

Preserve Login's SafeDelegatingFilterProxy, ContainerLogin, web.xml, SAML templates
and providers. No SAML change is required by source evidence.

Preserve Python auth.py/obo.py and their token audiences/OBO behavior. The mirrored
docs/mcp/development-lines/protocol/sakai_flow.py stays pinned; this plan changes
neither flow headers nor their client protocol.

Preserve AttachmentReachProof.java, AccessServletProof.java, their source evidence
and recorded failed outcomes. AttachmentReachProof inherits the changing chain
fixture; if that prevents compilation, create a separately reviewed compatibility
fixture adjustment without altering the failed assertion or acceptance status.
Do not claim untouched test behavior merely because the proof file itself did
not change.

## 23. Step-by-step implementation sequence

These steps are future work requiring an implementation instruction.

1. Reconfirm branch/HEAD/status and preserve unrelated changes. Recheck exact
   verifiers, registration callers, configuration and deployment manifests.
2. Record a reviewed path list and frozen original business/catalog fingerprints.
   Preserve failed attachment evidence and source anchors.
3. Add managed/shared dependency metadata and module declarations at existing
   versions. Inspect effective POM/dependency trees before editing auth code.
4. Transform DelegatedJwtVerifier into the small Spring configuration collaborator,
   porting synthetic token negatives to real NimbusJwtDecoder/provider tests.
   This intermediate change must not be released with both active validators.
5. Refactor guard to compose the standard context/bearer filters, then invoke its
   native adapter only on fresh authentication. Preserve native wrappers/leases.
6. Move verified identity data ownership into the bridge; adjust conversations
   references without changing its protocol/ownership logic.
7. Consolidate legacy route admission in DelegatedRoutes and the shared entry.
   Preserve its enabled gate, mandatory-bearer protection, audit attributes and
   original business handlers.
8. Remove legacy proxy/bean/filter/verifier and obsolete duplicate tests in the
   same integrated candidate. Prove both route groups reach the single provider.
9. Extend tests with real RequestFilter and servlet registration/forward behavior,
   including native OAuth1/Basic and SAML/browser regressions.
10. Run focused dependency/build/test gates and record honest results separately
    from runtime acceptance. Fix actual failures within the authorized auth scope.
11. Update role/source anchor and narrow allowed test metadata after reviewed code
    commits; keep extraction_anchor immutable. Add the plan/documentation path to
    metadata_allowlist for later documentation commits.
12. Prepare a separate exact-artifact release manifest and compatibility report
    only when deployment is requested. No runtime flag, route, or service starts
    implicitly as a consequence of local work.

## 24. Migration from the current implementation

| Current state | Target state |
| --- | --- |
| McpJwtVerifier and DelegatedJwtVerifier each build Nimbus/JWK machinery | One Spring decoder/provider configuration in shared auth module |
| Legacy custom bearer parser and shared custom bearer parser | Stock bearer resolver/filter; narrow transport hardening around version-specific gaps |
| Legacy filter swaps only current Session after RequestFilter | Shared native session selection before RequestFilter for both route groups |
| Two native identity/session implementations | One guard adapter with post-filter binder |
| legacy() bypasses the shared path | Explicit gated legacy admission into the same Spring/auth bridge |
| Verifier.Identity anchors conversation model | Bridge-owned verified identity record, no raw JWT in native state |
| No Spring delegated request context | Fresh stateless Spring context with standard finally cleanup |
| Different legacy response protection | Common credential envelope; compatibility tests for native errors and large results |

Default migration is a source-level replacement, not permanent dual validation.
Intermediate commits are not deployment candidates. Roll back a candidate by
restoring the previous reviewed full release artifact, not enabling an old verifier
inside the new runtime.

A material compatibility effect is that legacy results will now pass through the
shared response envelope and tighter mixed-credential policy. Characterize all
legacy resource/file responses, error status/body handling and large/compressed
outputs. The 1 MB buffer cannot silently break supported legacy exports. If a real
legacy route needs different bounded output handling, define that as explicit
route response policy within the SAME native bridge, with no second token
validator. Do not remove the envelope or allow credential-bearing streams by
default. This is an implementation acceptance blocker until characterized.

No requirement for concurrent old/new validators was found in the source. If a
future rolling release makes dual artifacts unavoidable, document exact old/new
artifact compatibility and deployment window; do not add two live verifiers to
one artifact as a convenience. Native shared JAR/WAR/classloader changes normally
need a coordinated release/restart using existing approved release procedures.

## 25. Tests to add/modify

No tests were run during this planning task. The following are future gates.

| Area / trigger | Required assertion |
| --- | --- |
| Browser session, no bearer | Same native user/session/parameters/cookies; no JWKS call or delegated session |
| Anonymous request, no bearer | Native anonymous behavior unchanged |
| Basic/OAuth1, no bearer | Existing native mechanism and ordering preserved |
| Valid delegated token | Real decoder/provider/filter success; correct UID/EID in SessionManager, ATTR_SESSION, HTTP session wrapper, principal/remoteUser and native service |
| Wrong signature/issuer/tenant/audience/algorithm | Rejected before native account lookup/handler; no downgrade or fallback |
| Expired/missing exp; future/missing nbf | Inherited exact policy and clock boundary tests |
| Missing/wrong scope; roles-only token | Authentication denied; no native permission grant |
| Identity shapes | Reject missing, scalar, empty/multi-value, non-string, blank, padded, controls, overlong claim |
| Missing/bad oid or tid | Rejected; no invalid flow/audit owner |
| Unknown EID / disabled user | Real UserAuthnComponent and directory fixture reject; not just a mocked null |
| Provider remap to other EID | Exact current contract rejects; no accidental support for Case B |
| Duplicate Authorization / mixed credential inputs | Reject before session creation; preserve ordinary non-bearer behavior |
| access_token query/form and malformed header | No alternative authentication transport or unintended ordinary form parsing |
| Legacy flag / existing HTTP flag combinations | Independent gates with one provider; protected legacy routes never execute anonymously |
| Spring auth exists but fresh bearer is absent/invalid | Stale or foreign authentication never activates native bridge |
| Native mapping fails after Spring succeeds | Handler never executes as anonymous/browser/other user; both contexts clean |
| JWT verification removed | No old class/bean/registration/production Nimbus processor imports; inspect package and actual graph |
| JWKS unavailable/malformed/rotating | Fail closed, sanitized status; cache/rotation behavior tested through Spring HTTP integration |
| Output wrappers | No session cookie/ID leakage in headers/body, fragmented error output, reset/redirect/compression/size cases |
| Legacy resources/exports | Existing allowed formats and bounds characterized under shared envelope |
| Native authorization | Actual Sites/Assignment/permission fixtures still deny unrelated site/user/group access |
| Flow replay/account disabled/expired | Fresh account check each call; owner isolation and end cleanup preserved |
| Registration and container | Actual initializer/XML chain and named-forward behavior, not class-existence assertions |

Keep synthetic signed tokens and controlled JWKS/HTTP fixtures. Tests should
exercise actual Spring filters/decoder/provider; mocking JwtDecoder alone does not
prove signature/issuer/claim policy. Native authorization tests should also call
representative real services, not merely assert a mock invocation.

Existing suites to retain/adapt include DelegatedChainTest, DelegatedResponseTest,
PortalContainerTest, ExistingSitesChainTest and LoginControllerTests. Source audit
changes must explicitly admit only Spring framework dependencies and continue
rejecting business APIs/persistence/advisors.

## 26. Build/dependency verification

Future commands, from this worktree root, using Java 17. These are proposed
verification commands, not a report that they ran.

    export JAVA_HOME=/opt/homebrew/opt/openjdk@17

    mvn -f apps/sakai/master/pom.xml help:effective-pom \
      -Doutput=/tmp/sakai-bearer-effective-master.xml

    mvn -f apps/sakai/pom.xml -pl mcp-auth,webapi -am \
      dependency:tree \
      '-Dincludes=org.springframework.security:*,org.springframework:*,com.nimbusds:nimbus-jose-jwt'

    mvn -f apps/sakai/deploy/pom.xml dependency:tree \
      '-Dincludes=org.springframework.security:*,org.springframework:*,com.nimbusds:nimbus-jose-jwt'

    mvn -f apps/sakai/pom.xml -pl mcp-auth,webapi -am \
      -DskipTests compile

    mvn -f apps/sakai/pom.xml -pl mcp-auth,webapi -am \
      '-Dtest=DelegatedBearerAuthenticationTest,Delegated*Test,PortalContainerTest,ExistingSitesChainTest,Mcp*Test,LoginControllerTests' \
      -Dsurefire.failIfNoSpecifiedTests=false test

    mvn -f apps/sakai/pom.xml \
      -pl mcp-auth,webapi,portal/portal-charon/charon,entitybroker/tool,assignment/tool,announcement/announcement-tool/tool,gradebookng/tool,content/content-tool/tool,login/login-tool/tool \
      -am -DskipTests package

    mvn -f apps/sakai/master/pom.xml -DskipTests clean install
    mvn -f apps/sakai/pom.xml -DskipTests clean install

Use reactor builds because sibling Sakai artifacts/descriptors are not assumed to
be published. Dependency reports against uninstalled siblings may initially need
the parent/reactor build; report that prerequisite, not a fictitious tree result.
Also inspect Login dependency:tree for security-web/config/core and SAML closure.

Inspect the built/staged shared library directory and WAR WEB-INF/lib contents:
one effective version per artifact, Framework 5.3.39, all generic bearer security
modules 5.7.14, Nimbus 9.37.4. Record parent/child classloader origins for
SecurityContextHolder, BearerTokenAuthenticationFilter, JwtAuthenticationProvider,
NimbusJwtDecoder and the bridge in the container fixture. Keep existing SAML
artifact versioning distinct from generic Spring Security version assertions.

Run the auth worktree's focused Python source-boundary test in its OWN environment:

    cd services/mcp
    uv sync --locked
    uv run --no-sync pytest tests/security/test_native_auth_boundary.py -q

The full existing MCP checks can then verify preserved host contracts. Run
verify_arrangement.py --current only once reviewed code/metadata commits and
anchors are consistent; it rejects uncommitted tracked changes and does not prove
runtime correctness. Review diff/whitespace and guidance with the existing
repository checks. Do not relax verifiers just to achieve a passing result.

Do not fold the deliberately failed attachment readiness proofs into a claim of
normal successful regression acceptance. If their inherited fixture must compile,
record that separately from executing or repairing the positive proof.

## 27. Browser/SAML regression tests

Before any authorized release, compare ordinary anonymous and authenticated
browser requests through actual native RequestFilter:

- Existing student/instructor session stays the same before and after API bearer
  requests on reused servlet threads.
- Native cookie issuance, login redirects, logout, requested return URL and normal
  form/CSRF processing are unchanged for no-bearer requests.
- Basic and enabled OAuth1 preserve their own identity and do not enter the new
  bridge. Mixed OAuth1/bearer cannot install a native advisor.
- LoginControllerTests continues to pass, but is not a substitute for SAML.
- Test Login's optional proxy with no SAML configuration, and, with a representative
  configured SAML fixture, test login initiation, assertion/provider success,
  ContainerLogin trusted-evidence convergence and logout.
- Confirm the new chain is not mapped to Login and does not overwrite browser
  Spring SecurityContext persistence on nested forwards.

The real deployment's IdP/browser round trip needs separately authorized integration
acceptance if unavailable locally. Record that limitation rather than calling
a synthetic SAML fixture a live Entra login pass.

## 28. Concurrency and cleanup verification

Use barrier-coordinated A/B requests through actual Spring and RequestFilter,
not merely serial calls to a bridge method. Assert UID, EID, HTTP session/context
session, ToolSession, current tool/placement, Spring JwtAuthenticationToken and
external owner values during each overlapping execution.

Reuse executor/container threads for A → invalid token → B → anonymous/browser.
After each request assert empty top-level Spring context and no delegated native
thread/request marker. Restore only legitimate caller state in genuine nested
dispatch; do not resurrect leaked top-level identities.

Inject failures at JWT decode, account resolution, login, native wrapper creation,
downstream execution, response.finish, lease.close/invalidate and nested forward.
Assert lock release and independent cleanup even when one stage fails. A native
exception swallowed by RequestFilter still must not bypass cleanup or emit secrets.

For flows test same-owner serialization, conflicting owner IDs, copied nonces
across A/B, session expiration/removal, end, 4/256 bounds and process restart
behavior. Preserve node affinity requirement; no claim of distributed locking.
Check native permission caches and usage/realm refresh effects under repeated
sessions. No tokens or Spring principals belong in persisted native state.

## 29. Security invariants

1. Raw JWT/header/claims are untrusted until Spring authentication completes.
2. The bridge only consumes fresh authenticated JWT results from its own boundary.
3. Exact configured resource/issuer/tenant/delegated scope and the inherited
   identity/time requirements remain enforced.
4. Native ExternalTrustedEvidence is identity adaptation, never token verification.
5. No caller-supplied UID/EID/header or token subject bypasses native user resolution.
6. Native account disabled/unknown/mismatch fails before handler execution.
7. Scope admits a credential to the authentication capability; native services
   alone decide site/course/resource authorization.
8. No new native business endpoint/service/model/schema/permission advisor.
9. Both route groups share one JWT authentication implementation with independent
   feature gates and explicit narrow reach.
10. A no-bearer ordinary request retains native/browser semantics.
11. Owned delegated Session and Spring context cannot leak across requests,
    concurrent actors, nested dispatch boundaries or servlet-thread reuse.
12. Native session credentials never become client credentials; no JWT/Sakai
    credentials appear in logs, redirects, errors or browser session storage.
13. Every flow request is freshly token/account authenticated; flow nonce is
    neither a login credential nor a business transaction lock.
14. Failures never fall back to legacy validation, cookie user, anonymous execution
    of a protected handler, or privileged account.
15. Shared-library changes must preserve normal SAML/Login and native class loading.
16. Planning/local test results never establish deployed runtime acceptance.

## 30. Risks/open questions

| Question/risk | Evidence and required disposition |
| --- | --- |
| What is actually deployed now? | Historical legacy release evidence exists; shared worktree role says no accepted runtime. Before release, read-only artifact/commit/JAR/flag inventory is required. This plan did not contact the VM or infer live code from main |
| Is a runtime AuthenticationIdUDP active? | Default provider XML examples are commented and deployment overrides can differ. Confirm active provider/mapping uniqueness read-only; current plan needs no new mapping |
| Legacy output compatibility | Shared 1 MB response buffer, opaque compression rejection and mixed-cookie restrictions are stronger than legacy behavior. Characterize all original resource/export paths before replacing the legacy filter; do not broaden streams silently |
| JWKS fetch resource limits | Current custom ResourceRetriever has 2-second connect/read and 1 MB document cap. Spring builder supports RestOperations/timeouts/cache, but no equivalent max-document-size setter was found. Preserve the cap through a small bounded HTTP response adapter using existing HTTP/IO utilities if required; do not introduce a new JWK client. Test chunked/false-length responses |
| Time policy | Stock symmetric 60-second leeway would broaden exp acceptance. Preserve strict-exp/presence predicates unless a separate explicit policy decision changes it |
| Normal parameter behavior | Spring 5.7 resolver reads access_token parameters despite disabled transport. Header-only projection/no-bearer fast path needs actual request parsing tests |
| Duplicate headers | Stock resolver uses getHeader; project transport policy must reject duplicate/mixed Authorization without reimplementing bearer grammar |
| Native exception behavior | RequestFilter can swallow downstream exceptions. Cleanup/credential protection tests must cover observed response behavior |
| Thread/native permission caches | Outer native clear is broad; guard restores selected keys. Confirm no account-dependent cache or advisor survives into an unrelated request |
| Shared vs Login-local security-web | New shared artifact and Login-local same-version libraries can affect classloading. Verify container origins and SAML behavior; do not remove Login dependencies speculatively |
| Failed attachment proofs | They remain failed/unaccepted; shared refactor does not add /access reach. Preserve evidence and avoid accidental proof fixture breakage |
| Role preservation checks | Existing verifier allows only one original Python audit test delta and excludes some auth-specific Java test paths. Future narrowly reviewed metadata changes must accommodate actual auth test migration while preserving business/catalog checks |
| New route needs from tool line | Tool line may request additional credential reach, but this task must not silently widen it. Record a separate compatibility requirement and test it deliberately |
| Optional azp/appid restriction | Current implementation does not require it. Introduce only for an explicit caller restriction with correct OBO/token-version evidence |

The architectural choice is settled by source: authenticate with standard Spring,
select the native Session before RequestFilter, and validate/align native request
context afterward. Remaining questions are compatibility and acceptance gates;
none requires changing Sakai core authentication or authorization classes.

### Investigation record

Read-only work included Git/worktree/role state; all seven custom auth sources;
their actual Java/XML registrations and test callers; Spring/Sakai managed
dependencies and published versioned dependency metadata; native authentication,
directory, session, usage, security/thread/tool implementations and bean wiring;
representative Sites/Assignment consumers; Login SAML templates/proxy/ContainerLogin;
native OAuth1 filters; and existing token/release/worktree evidence.

Spring 5.7.14 source was inspected at its version tag (links above); research
downloads were kept in a task-specific /tmp directory, outside repository source.
No Maven compile/package/test, application startup, live token operation, Entra
change, Azure change or deployment was performed. This plan is the deliverable.
