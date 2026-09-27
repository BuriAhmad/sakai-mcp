# Phase 11 — Sakai HTTP adapter (2026-09-27)

Status: **PASS for isolated client checks; live adapter smoke belongs to Phase 8**.

`services/mcp/src/sakai_mcp/sakai_client.py` builds only fixed-origin Sakai integration URLs from trusted configuration and bounded, encoded path segments. Each call obtains a fresh delegated token through the OBO provider and propagates a generated correlation ID. The adapter uses explicit connect/read/write/pool and overall time bounds, a one-megabyte response cap, JSON shape checks, and stable error codes. Read operations make at most three attempts on transient dependency failures. The sole write, announcement creation, makes one attempt; uncertain response, 5xx, and read/write timeout outcomes are reported as `AMBIGUOUS_WRITE_OUTCOME` without replay.

Mock-transport tests cover successful read/write, fixed host and delegated bearer/correlation headers, 401/403/404/409/429 mapping, read retry, pre-connect write failure, post-send ambiguous write timeout, 5xx and malformed write response, invalid course ID, and oversized response. All 30 combined service tests passed; Ruff and mypy passed. No live Sakai call is claimed by these tests. No token, personal identifier, site ID, content, or grade is retained in this report.
