# Phase 1 Sakai 25.2 source reconnaissance — 2026-09-26

Status: **PASS for Phase 1 source/release reconnaissance**. This defines the request lifecycle to implement and test. It is not proof that delegated bearer requests work; no bearer integration was added.

## Build and runtime relationship

`.github/workflows/sakai-source.yml` compiles the parent and full Sakai tree with Java 17 and `-DskipTests`. `scripts/deploy-sakai-release.sh` archives an exact commit from pushed `origin/main`. `deployment/release-sakai-vm.sh` builds that source on the VM with `/opt/maven/bin/mvn`, stages Tomcat `webapps`, `components`, and `lib`, swaps those directories, waits for local `/portal`, and records the commit in `/opt/sakai-releases/current`. The local wrapper also checks public HTTPS. `docs/INFRASTRUCTURE.md` records Tomcat 9 and the Sakai 25.2 import baseline.

## Authentication and session facts from tracked source

| Question | 25.2 source finding |
| --- | --- |
| External trusted evidence | `login/login-tool/tool/src/java/org/sakaiproject/login/tool/ContainerLogin.java` constructs `ExternalTrustedEvidence` from container `getRemoteUser()` and calls `AuthenticationManager.authenticate`, then `UsageSessionService.login`. Evidence itself only wraps a string (`kernel/api/.../ExternalTrustedEvidence.java`); it does **not** validate Entra tokens. |
| Identifier lookup | `kernel/kernel-impl/.../UserAuthnComponent.java` calls `UserDirectoryService.getUserByAid(identifier)` and rejects a user with property `disabled=true`. `BaseUserDirectoryService.getUserByAid` uses `AuthenticationIdUDP` when configured, otherwise falls back to `getUserByEid`. This runtime provider choice and mapping uniqueness must be checked before using the bridge. |
| Current HTTP session | `webapi/.../WebAppConfiguration.java` maps Sakai `RequestFilter` to `/*` before the Spring dispatcher. `RequestFilter.assureSession` resolves or starts a Sakai session, attaches it to the request, and calls `SessionManager.setCurrentSession`. |
| Current user and usage session | `UsageSessionServiceAdaptor.login` starts a usage session, writes user ID and EID into the current Sakai session, refreshes authorization groups, and posts a login event. `SessionComponent` stores current session and tool session through `ThreadLocalManager`. `webapi/.../LoginController.java` follows `startSession` → `setCurrentSession` → `usageSessionService.login` for password login. |
| Cleanup | `RequestFilter` clears `ThreadLocalManager` in its outer request `finally`. `UsageSessionServiceAdaptor.logout` invalidates the **current Sakai session**; `MySession.destroy` removes it and clears its current-session binding. A bearer path must not call `logout` on an unrelated browser session. |
| Ordinary login independence | Container and password login are separate existing paths. A future bearer adapter can be confined to `/api/mcp/v1/*` inside WebAPI, after `RequestFilter` and before MCP controllers, without changing either login implementation. Filter ordering and response cookie/session behavior require focused tests. |

## Candidate lifecycle to test before implementation

After Sakai's outer `RequestFilter`, a path-scoped WebAPI filter would validate the downstream bearer token first, resolve the mapped user, create a distinct short-lived Sakai session, bind it as current, call normal `UsageSessionService.login`, execute the MCP controller, invalidate that distinct session in `finally`, then restore the previous current-session binding. The outer `RequestFilter` will subsequently clear the thread locals. This is a **candidate only**: prove filter order, no browser-session mutation, usage-session close, cookie behavior, and exception cleanup in focused tests before writing production authentication code.

Runtime inspection found deployed `sakai-kernel-impl` and `sakai-provider-pack` components and an active WebAPI/Tomcat service. The Sakai runtime properties did not name a user directory provider in the inspected keys. The provider pack contains sample/demo and other provider XML definitions, so the exact active provider must still be checked by a controlled mapping test. Phase 7 must verify the candidate lifecycle with focused tests, including filter order, no browser-session mutation, usage-session close, cookie behavior, exception cleanup, and provider-specific AID/EID mapping. No runtime configuration values or user data were copied into this note.
