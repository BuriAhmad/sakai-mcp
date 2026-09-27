# Phase 13 — MCP audit and redaction (2026-09-27)

Status: **IN PROGRESS; local structured audit and redaction PASS; Azure telemetry NOT RUN**.

Each tool call emits a JSON record with UTC timestamp, generated request ID, tool name, read/write classification, pseudonymous SHA-256 actor/course/target/created-object references, stable outcome code, elapsed milliseconds, and optional revision/commit metadata. The same request ID is sent to the Sakai integration as `X-Correlation-ID`. Raw tenant/object/Sakai IDs, bearer tokens, grades, submissions, announcement title/body, and private credentials are omitted. HTTPX/HTTPCore URL INFO messages and expected SDK tool-error INFO messages are suppressed because they can contain raw paths or tool inputs. The failure path logs a category, never an exception message or token endpoint detail.

The local redaction test passed with synthetic token, user, course, created object, and body markers absent from captured audit output. The composed service tests remained green. Container Apps log collection and any Azure OpenTelemetry configuration are deferred to the runtime infrastructure phase; no cloud audit claim is made here.
