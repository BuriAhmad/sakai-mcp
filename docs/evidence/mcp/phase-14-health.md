# Phase 14 — MCP health contract (2026-09-27)

Status: **PASS for local ASGI probes; cloud probe execution NOT RUN**.

Unauthenticated `GET /live` returns HTTP 200 `{"status":"live"}` when the process/event loop can serve requests. Unauthenticated `GET /ready` returns HTTP 200 `{"status":"ready"}` after the app has been constructed with valid local settings and credential files. Neither route calls Sakai, Entra, or Key Vault during a request. A transient dependency outage therefore does not make a running replica fail liveness/readiness and enter a restart loop. Both routes passed a local ASGI test; deployment probe definitions belong to the later Container Apps Bicep milestone.
