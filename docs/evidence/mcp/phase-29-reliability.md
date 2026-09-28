# Phase 29 — reliability and failure modes (2026-09-28)

Status: **PASS for the runbook's bounded reliability gate**, with the scope of injected faults stated below. Phase 25 client acceptance remains open.

## Fault matrix

| Boundary | Injection / observation | Result |
| --- | --- | --- |
| Inbound Entra/JWKS | Invalid, expired, wrong issuer/audience/scope and unavailable signing key in existing `test_auth.py` | Fail closed; no Sakai call. JWKS outage cannot authenticate until lookup recovers. |
| Entra OBO | Synthetic token endpoint failure and downstream signing-key lookup outage in `test_obo.py` | No static/admin credential fallback or inbound-token forwarding. A downstream JWKS connection failure now maps to sanitized `DEPENDENCY_UNAVAILABLE`; a subsequent good lookup succeeds. |
| Sakai unavailable/timeout | Mock connect and read timeouts | GET: exactly three bounded attempts, then `DEPENDENCY_UNAVAILABLE`; restored dependency succeeds on the next call. |
| Sakai 503 | Existing transient-read test | GET succeeds on the third and final permitted attempt. |
| Sakai 429 | Mock response | Stable `RATE_LIMITED`; one attempt, no retry storm. |
| Malformed/oversized Sakai body | Invalid JSON, >1 MB streamed body, oversized declared content length | Sanitized `INTERNAL_ERROR` on reads; bounded consumption. |
| Announcement response lost after commit | Existing simulated committed POST with read timeout | Exactly one POST; `AMBIGUOUS_WRITE_OUTCOME`; read reconciliation found the one object. No automatic replay or title-based deduplication. |
| POST timeout/5xx/malformed result | Existing adapter tests | One attempt; ambiguous outcome. Pre-connect failure is dependency unavailable. |
| Audit context/error | Injected exception in `audit_call` | Structured `INTERNAL_ERROR` without private exception/body text; request and created-object context variables reset. |
| Health/readiness | Source test and live probes | `/live` and `/ready` are local startup probes; they remain independent of transient Entra/Sakai health. Authenticated operations report downstream failure separately. |

`uv run --no-sync pytest -q` passed **50/50** after the focused fix; Ruff and mypy passed. The fix is tracked at `fc46121b7f72060de359f8c25865239ffdabf870`. The manual [exact-commit MCP release](https://github.com/BuriAhmad/sakai-mcp/actions/runs/36397652095) built and scanned that commit, pushed digest `sha256:efffa5df07eb14d65486150e01b45189cd6567201450b436c4970778f6738c6b`, and deployed ready revision `ca-mcp-sakai-dev--0000007` on the verified `Azure for Students` subscription. Scan summary: zero critical, zero fixable high, zero secrets; **44 high without published fixes** in the image. The prior digest was `sha256:f3efe77f2596473a69ceaf848b61b2b097ff360330736ce4e780e7cf7a86b28b`.

The release gate passed public TLS `/live` and `/ready`, Bearer challenge, canonical resource metadata, selected digest/commit, ready revision, SNI binding, and affinity `none`. A fresh synthetic Student A delegated token then completed a deployed `list_my_courses` read through MCP, OBO, and Sakai. A separate sequence of public read-only health calls observed one connection refusal between successful calls during scale-from-zero/revision activity; three immediate `/ready` repeats returned 200. This is a bounded observed transient, not a claim of zero cold-start failures. Live Azure shows revision `0000007` ready, the selected digest, and scale 0/2. Phase 26 already proved cross-replica statelessness on the previous runtime code; this release changed only downstream JWKS error classification.

Faults were injected through local mock transport and signed synthetic tokens, avoiding live Entra/Sakai disruption or durable data corruption. There was no live forced Sakai outage, JWKS outage, or container restart. Read retry latency is bounded by the configured per-attempt network/response timeout and three attempts; writes remain single-attempt. A real ambiguous create still needs human/client reconciliation against Sakai state before any separate new request.
