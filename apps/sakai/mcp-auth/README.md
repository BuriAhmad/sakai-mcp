# Delegated bearer authentication and native Sakai sessions

This shared authentication-only JAR uses Spring Security **5.7.14**, Sakai's
Spring Framework **5.3.39**, and managed Nimbus **9.37.4**. The
[approved plan](../../../docs/mcp/sakai-bearer-auth-refactor-plan.md) and
[implementation report](../../../docs/mcp/sakai-bearer-auth-refactor-implementation.md)
record the migration and validation limits. Work in this auth development tree;
see [ownership](../../../docs/DEVELOPMENT_WORKTREES.md).

## Request flow

`DelegatedCredentialGuard` composes Spring's stateless
`SecurityContextHolderFilter(NullSecurityContextRepository)` and
`BearerTokenAuthenticationFilter`. A `ProviderManager` with one
`JwtAuthenticationProvider` authenticates through `NimbusJwtDecoder`.
`DelegatedBearerAuthentication` configures those standard objects; it implements
neither JWT decoding nor a JWKS client. Both old custom verifier classes and the
legacy `McpBearerFilter`/proxy registration have been removed.

Only a freshly authenticated `JwtAuthenticationToken` enters the native bridge:
validated singleton identity claim → `ExternalTrustedEvidence` → native
`AuthenticationManager`/`UserDirectoryService` → registered isolated Sakai Session
and `UsageSessionService.login`. The internal session cookie selects that Session
**before RequestFilter**. `DelegatedSessionFilter`, after RequestFilter, checks
native session/UID/EID consistency and aligns HTTP principal/remote-user and the
current request. Existing Sakai services enforce all business permissions.

Ordinary requests without bearer credentials pass unchanged. SAML/Login wiring
and Sakai core classes are unchanged. Legacy `/api/mcp/v1/*` retains mandatory
bearer authentication and `mcp.integration.enabled=false` by default. Selected
existing HTTP interfaces independently require
`mcp.integration.existingHttp.enabled=false` by default. These gates select
credential reach, never different JWT implementations.

## Reading the implementation

Start with `DelegatedCredentialGuard.doFilter`: it checks for an already bound
native dispatch, passes ordinary requests through, and applies bearer route and
configuration checks. `authenticateBearerAndContinue` then asks Spring to verify
the token. Its successful callback calls `executeWithDelegatedSession`, which
resolves the Sakai account, opens the native session, runs the remaining chain,
and cleans up before sending the response. `restorePreviousContext` restores the
caller's thread values and request attributes even when processing fails.

`DelegatedRoutes.isCustomMcpEndpoint` identifies `/api/mcp/v1/*`; this was previously
named `legacy`. It is a route category, not a second authentication implementation.
`allowsExistingHttpEndpoint` describes the selected standard Sakai API policy.
`allowsToolSessionRequest` describes the separate optional multi-request policy.
`DelegatedConversations.open` handles both ordinary single-request sessions and
optional flows: no flow header takes the single-request path immediately.
These names and comments do not change endpoint mappings, feature switches,
token requirements, permissions or session cleanup.

## Token and transport policy

The existing `mcp.integration.issuer`, `.tenant`, `.audience`, `.scope` and
`.jwksUri` properties configure one downstream Sakai resource policy. Issuer/JWKS
must be trusted HTTPS URIs. RS256 is explicit. Validators require exact issuer and
tenant, exactly one matching audience, delegated `scp`, canonical bounded `oid`,
and the observed singleton string-array identity. Optional
`mcp.integration.identityClaim` defaults to `extn.SakaiEid`. There is no UPN/email
fallback or new AID mapper; resolved native EID must equal the validated claim.

`exp` and `nbf` remain required: expiration is strictly after now; not-before has
60 seconds of leeway. Spring owns timestamp validation with explicit presence
and strict-expiration policy predicates. Scopes do not become Sakai roles.

Bearer syntax/extraction belongs to Spring's resolver. A header-only projection
avoids Spring 5.7's parameter inspection; query/form tokens are never accepted.
The outer guard preserves duplicate-header/16,384-character token bounds,
rejects mixed cookies/container/session/OAuth1 credentials and applies explicit
route/placement limits. Key HTTP reads retain 2-second connection/read timeouts
and a 1 MB actual-stream limit, including chunked bodies. Failures return sanitized
401/challenge, 403 account/policy denial, or 503 dependency/configuration failure.
`BoundedJwkSetResponse` implements only the bounded HTTP response stream; Spring
still owns JWT decoding and JWKS retrieval.

## Native lifecycle and output

`DelegatedConversations` retains the pinned flow protocol: freshly authenticated
owner on every request, opaque HMAC session selection, 4 actor/256 node limits,
5-minute maximum age, 60-second inactivity, per-flow serialization, explicit end
and native expiry cleanup. Native permission checks and CSRF/tool state remain.
No raw JWT or Spring context is stored in a native Session. Node affinity remains
required; these locks are not business transaction locks.

`DelegatedResponse` protects the complete native chain and postprocessing. It
buffers 1 MB normally; only existing custom MCP file/artifact GET paths use the native
10 MiB per-file cap. It suppresses session credentials/cookies and rejects leaked
session IDs, oversized or unsupported/compressed output. Body emission follows
owned-session cleanup and native restoration; cleanup failure yields empty 502.

WebAPI's narrowly scoped `DelegatedStreamingConfiguration` executes only a bound
custom MCP artifact `StreamingResponseBody` synchronously under this same guard.
Other MVC streaming behavior is delegated to Spring unchanged. No upstream
controller or async security-context propagation is introduced.

## Failure diagnostics and maintenance

`DelegatedDiagnostics` emits a fixed stage name for internal configuration,
key-service, session, handler, cleanup, restoration and response failures. It
accepts only a closed enum: no request, identity, token, session ID, exception
message/stack or response body is passed to the logger. Ordinary credential and
permission denials retain their existing response behavior. The diagnostics
logger remains available when sensitive native DEBUG logging causes a bearer
request to be refused.

Test Mockito Core and Inline both use Sakai's managed `${sakai.mockito.version}`;
production Spring/Nimbus versions and shared-library scopes are unchanged. Record
future refactors in [the repository log](../../../docs/REFACTOR_LOG.md).

## Verification and release boundary

Use Java 17 and the reactor; commands/results are in the implementation report.
Tests exercise real Spring/JWK processing, actual RequestFilter chains, native
account rejection, concurrent identities, servlet registration, Portal named
forwarding and synchronous MVC artifacts. Native domain implementations,
Python/OBO runtime, catalogs/contracts and evaluator remain unchanged.

The historical positive attachment proof remains failed/unaccepted; no `/access`
reach was added and no failed proof source/evidence was repaired. See
[preserved extraction evidence](../../../docs/mcp/development-lines/extracted-auth-readme.md).
The mirrored Python flow helper under `docs/mcp/development-lines/protocol/` is a
reference pin, not an import across worktrees. Nothing in this refactor enables
flags, configures Entra, changes Azure, deploys, or establishes live acceptance.
