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
tests or changing Sakai source; final results are recorded below when complete.

## Execution status

Prepared; deployment and live tests pending completion of the CI gate.
