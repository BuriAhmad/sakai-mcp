# Auth cleanup development release — 25 October 2026

## Authorization and source

The user authorized deployment of the reviewed auth cleanup and testing it on the
running development environment. Use `codex/auth-development`; main stays at the
original baseline. Cleanup code is `7da57f49`, documented with the before/after in
[the refactor log](../../REFACTOR_LOG.md). The release runner's durable unit change
is `c1f6712a0b679bc214fa8629f44bef372857284c`, with separate verification in that log.

The currently installed release at preflight was
`20261024T163517Z-2844430a44cf` / `2844430a44cf5cf0896ca05c522f7fe4f04c16bd`.
VM Tomcat was active; free disk space was 32 GiB. The selected subscription is
`55a5701c-411e-45f1-9829-9c80f526d9eb`, group `rg-sakai-mcp-dev`.

## Why wrong-password API requests return 500

The unmodified password controller calls native AuthenticationManager.authenticate
before starting a session. A wrong password throws native AuthenticationException.
There is no specific handler for it, so the generic Exception handler maps it to
HTTP 500. Authentication stays denied and no authenticated session is created.
The normal native HTML login form has its own handling and works correctly.

This is present in the official imported Sakai 25.2 source, not introduced by the
project auth code. The two local files have no changes since import `e092fa04`.
The relevant upstream source at the recorded source SHA was also inspected:
[LoginController](https://github.com/sakaiproject/sakai/blob/b5b7800f0fcddf9d0db47276a66065189365d905/webapi/src/main/java/org/sakaiproject/webapi/controllers/LoginController.java),
[GlobalExceptionHandler](https://github.com/sakaiproject/sakai/blob/b5b7800f0fcddf9d0db47276a66065189365d905/webapi/src/main/java/org/sakaiproject/webapi/exception/GlobalExceptionHandler.java).
No error-mapping change is included in this release.

## Build gate and preparation

The local cleanup suite passed 107 Java tests, eight source-boundary tests and a
focused package reactor. Core and Inline Mockito both resolved to managed 3.12.4.
GitHub run `40123582368` attempt 1 failed fetching Maven jar plugin 3.3.0 from
Central before compiling the authentication changes. The artifact independently
returned HTTP 200 during preparation. The failed job was rerun without weakening
tests or changing Sakai source. Attempt 2 passed: full application build, 203
Chromium tests across 66 files, and the 107 focused Java tests. See
[CI run 40123582368](https://github.com/BuriAhmad/sakai-mcp/actions/runs/40123582368).
The selected release has identical `apps/sakai/` source to this CI revision
`fce55272`; subsequent commits change release tooling and documentation only.

## Execution status

**Deployed and healthy.** Selected commit:
`0c8767980ce8a9af210d9b41b51c5c1959542451`, branch `codex/auth-development`.
Release: `20261024T192919Z-0c8767980ce8` (UTC date 24 October, local date 25 October).

Commands:

```bash
./sakai deploy HEAD --branch codex/auth-development --check-only
./sakai deploy 0c876798 --branch codex/auth-development
```

The full 455-module Maven reactor reported BUILD SUCCESS. Unit
`sakai-release-20261024T192919Z-0c8767980ce8.service` completed with
`ActiveState=active`, `Result=success`; the release recorded `healthy` and the CLI
confirmed public HTTPS portal availability. A separate long-lived read-only SSH
progress monitor timed out after the build; the VM-owned release completed without
manual recovery. Original webapps/components/lib rollback directories are present.

The VM is running, MySQL is Ready with public access disabled, and MCP is Running
at its existing capacity. Main remains `208d69ac624910a29a7529934ddcc18bbac853e8`.
No additional old-release cleanup, Entra, schema, application property or MCP
capacity change was performed. No academic records or content were written.

## Installed artifact verification

The installed auth JAR contains BoundedJwkSetResponse and DelegatedDiagnostics,
confirming this cleanup reached the runtime. No McpBearerFilter, McpJwtVerifier or
DelegatedJwtVerifier remains in the auth/API/login artifacts; no auth test classes
are packaged. Exactly one production Sakai JWT authentication pipeline remains.

The shared runtime contains one checked version each: Spring Framework core,
beans, context and web 5.3.39; Spring Security core, web, OAuth2 core, JOSE and
Resource Server 5.7.14; Nimbus 9.37.4. The API WAR does not embed a duplicate
security/Nimbus copy.

| Installed artifact | SHA-256 |
| --- | --- |
| sakai-mcp-auth-25.2.jar | `bd9d06d23d90e6d9b32e621127686b4cbac4fff79e814f976dc456cd816290f0` |
| api.war | `c7032d06494e43dbb3ae60c20e252ae5ddff79a4be125bd77da701f9ce1761d5` |
| sakai-login-tool.war | `d2d93917e678b902b050001b7ed2a380aebf71c41ae1af13c574448994deca46` |

## Post-deployment tests

The Java 17 focused reactor was rerun after deployment:

```bash
mvn -B -ntp -f apps/sakai/pom.xml -pl mcp-auth,webapi -am \
  '-Dtest=DelegatedBearerAuthenticationTest,Delegated*Test,PortalContainerTest,ExistingSitesChainTest,Mcp*Test,LoginControllerTests' \
  -Dsurefire.failIfNoSpecifiedTests=false test
# From services/mcp:
uv run --no-sync pytest -q tests/security/test_native_auth_boundary.py
```

Result: **107 Java tests passed**, zero failures/errors/skips; **8 boundary tests
passed**. Tests were not weakened to accommodate the known API status issue.

The local live read-only harness acquired fresh real upstream and OBO tokens for
four synthetic student/instructor principals and made HTTPS requests to the new
release. Its private fixture inputs and credentials were kept outside Git.
**93 checks: 89 passed, 4 failed**, with the failures limited to the pre-existing
wrong-password `/api/login` HTTP 500 mapping described above.

| Exercise | Result |
| --- | --- |
| Four genuine OBO token acquisitions and issued canonical EID matches | Passed |
| Four API password logins, exact user identities, own portal and logout | Passed |
| Four actual native HTML form logins/logouts; incorrect HTML password | Passed |
| Wrong API password creates no authenticated identity | Passed for all four |
| Incorrect API password returns a client authentication error | Failed for all four: HTTP 500 |
| Cookie alone denied on bearer route; cookie plus bearer denied without changing browser identity | Passed |
| Own courses/announcements allowed; foreign courses absent and announcements denied | Passed |
| Submission access allowed only to the relevant instructor | Passed |
| Students read their own distinct released grades | Passed |
| Genuine wrong-audience token and tampered identity signature rejected | Passed |
| Caller identity header cannot widen access; no bearer session cookie; next tokenless request denied | Passed |
| Sixteen interleaved student grade reads, with invalid-token and tokenless follow-ups | 16/16 passed |

The connected MCP course-list tool also returned the expected two courses. Its
first call returned a tool error; the immediate retry succeeded. No persistent
failure was reproduced; this observation does not establish the transient cause.

## Remaining acceptance limits

The four API status failures remain open upstream behavior; authentication itself
is denied. This release deliberately does not change native LoginController or
GlobalExceptionHandler. SAML is not configured in this environment; tests exercised
ordinary IdPwd/browser authentication, not an IdP round trip.

The selected existing-HTTP and flow capabilities remain disabled. Their live
acceptance is not established by legacy route checks. Historical attachment
positive proofs remain failed/unaccepted and unchanged. No writes, grading
save/return, export/download or full end-user workflow acceptance is claimed.
Local validator tests cover additional token failure cases; this live run did not
mint every possible invalid-claim token. This is a tested development release,
not full production or tool-migration acceptance.
