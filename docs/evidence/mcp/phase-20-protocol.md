# Phase 20 — deployed MCP protocol/conformance (2026-09-28)

Status: **PASS for the project's fixed five-tool server surface.** This is a scoped server assessment, not a claim that the server implements every optional conformance fixture or extension.

The source checkpoint at test time was `0542669449865ecad668c130813ea858e230b4cd`; the deployed source remained `d1b32280c3ca0bfc590b51d95d8adf667ecd293f`, revision `ca-mcp-sakai-dev--0000004`, image `acrsmcpdevo6wzl5rvdbkwc.azurecr.io/sakai-mcp@sha256:f3efe77f2596473a69ceaf848b61b2b097ff360330736ce4e780e7cf7a86b28b`. No source or runtime change was needed. Local service SDK: MCP Python **2.2.0**. Official conformance runner: source **0.2.0-alpha.11**, Git commit `7169291ec0b68eb370fddcd9947313ab0d5e4156` (the npm registry's latest published 0.1.16 did not yet accept the current revision). Inspector registry version: **2.8.0**, recorded but not run; interactive client acceptance belongs to Phase 25.

The [2026-07-28 versioning specification](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning) removes initialization from the modern wire and requires per-request `_meta` and matching HTTP headers. The [2025-11-25 lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle) still uses `initialize`. Tests used fresh synthetic Student A Entra tokens; an ephemeral localhost proxy added that bearer to official conformance requests, forwarded all protocol bodies/headers unchanged to the canonical deployed `/mcp`, and was not a substitute server. No token was printed or retained in Git.

| Deployed check | Result |
| --- | --- |
| Modern `server/discover`, 2026-07-28 per-request metadata and headers | HTTP 200; tools capability advertised; stateless request accepted |
| Official 2026 `tools-list` scenario | 4/4; valid schema and deterministic order |
| Official 2026 `http-header-validation` scenario | 14/14; mismatched/missing method and name headers rejected correctly |
| Official 2025-11-25 `server-initialize` scenario | 2/2; version echoed, response schema valid |
| Published 0.1.16 2025-11-25 initialize and tool list | 1/1 each |
| Manual legacy negotiation | `initialize` echoed 2025-11-25, 2025-06-18, and 2024-11-05; unsupported 1900-01-01 and handshake-shaped 2026-07-28 returned HTTP 400 |
| Manual tool call | `list_my_courses` returned a successful result on both modern and legacy wire forms; unknown method returned JSON-RPC `-32601`; unknown tool returned `isError=true` |
| Modern malformed requests | Official stateless scenario passed missing `_meta`, missing required fields, version mismatch, header mismatch, and removed-method checks |

The broad official `server-stateless` scenario initially reported **22/28**, with six failures. Its missing-capability, progressive-stream, and no-log probes require diagnostic tools such as `test_missing_capability` and `test_logging_tool`; adding these would violate the fixed V1 catalog. Two failures concerned a `subscriptions/listen` stream through the first local auth proxy, which buffered streaming responses. The fixed catalog does not change and the five tools use no subscriptions, sampling, elicitation, roots, or other server-to-client functionality. No full-suite or Tier 1 conformance certification is claimed. The focused scenarios above establish the required transport and protocol semantics for the exposed tools. Legacy stateless HTTP mode has no standing server-to-client channel; none of the five tools depends on one.

### Subscription follow-up after Phase 24 (same day)

A later inspection found that the SDK's modern `server/discover` advertises `listChanged` and `resources.subscribe`, so the earlier proxy-based subscription failures could not safely be labeled mere fixture gaps. A direct authenticated **deployed** `subscriptions/listen` request used the 2026-07-28 metadata and HTTP headers and received HTTP 200 `text/event-stream`; its first event was `notifications/subscriptions/acknowledged` with a subscription ID. The first proxy had buffered SSE until completion, preventing the conformance runner from observing this ack. A streaming proxy retest still reported 22/28 with subscription/progressive-stream observation gaps and diagnostic-tool probes; it did not demonstrate a deployed subscription failure. The V1 catalog is static and no tool publishes list-change events or depends on subscriptions. This resolves the apparent conformance defect without changing the runtime or weakening the five-tool boundary. Full optional-stream conformance remains unclaimed.

The current SDK advertises prompts/resources in discovery even though this project registers none; their empty lists do not expose extra tools. Client UX, approval behavior, and caching beyond the protocol result remain later gates.
