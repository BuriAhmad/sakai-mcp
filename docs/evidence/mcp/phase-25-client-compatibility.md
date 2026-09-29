# Phase 25 — client compatibility and approval (2026-09-28)

Status: **IN PROGRESS / awaiting manual native OAuth and human approval testing**. The existing test client is now configured for Inspector's exact Web callback. No native OAuth, client-side cancellation, or approved-write result is claimed. Phases 26 and 27 were tested independently and checkpointed; their server results do not close this client gate.

## Current product facts checked before client claims

- Official [MCP Inspector 2.8.0 release](https://github.com/modelcontextprotocol/inspector/releases) is dated 2026-09-23. Its [CLI reference](https://github.com/modelcontextprotocol/inspector/blob/main/clients/cli/README.md) documents remote Streamable HTTP, modern/legacy era selection, static OAuth client configuration, and interactive callback defaults. It is a diagnostic client, not a model host with per-tool approval UX. The documented web callback is `http://localhost:6274/oauth/callback`; CLI/TUI default to `http://127.0.0.1:6276/oauth/callback`.
- Official [Claude custom connector instructions](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) dated 2026-08-11 say remote MCP connectors are available for the account tiers listed there and are brokered from Anthropic's cloud. The [current connector permissions guide](https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities) describes `Needs approval`, `Always allow`, and `Blocked` per-tool settings. Those are documentation facts, **not** observed Sakai connector behavior. Claude Desktop is available locally, but no Sakai remote connector was registered or authenticated during this phase.
- The [current ChatGPT developer-mode guide](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt) describes full MCP/write beta for Business, Enterprise, and Edu, and says write confirmation can depend on permissions/context. This account/workspace configuration was not tested, so ChatGPT compatibility is unclaimed.

## Empirical client diagnostic

The actual published Inspector **2.8.0 CLI** was run with modern 2026-07-28 era against an ephemeral localhost proxy forwarding unchanged MCP bodies/headers to `https://mcp.smartdigest.app/mcp` and injecting a fresh synthetic Student A bearer in memory. `tools/list` exited 0 and returned exactly the fixed five V1 names. A `list_my_courses` call later exited 0 and returned a successful nonempty structured course result. The first attempted read returned a proxy-side HTTP 500, then the retry of this **read-only** operation succeeded; the diagnostic bridge was not counted as an OAuth or reliability acceptance result. The local proxy was stopped afterward. No write was issued by Inspector.

The proxy deliberately bypassed Inspector's own OAuth flow, so this demonstrates only CLI transport/catalog/read behavior with a pre-obtained delegated token. It does **not** establish native client connection/authentication, approval display, Cancel/Reject, Allow/exactly-one create, persistent allow, or autonomous-mode behavior. Inspector is not claimed as an approval-enforcing host. No compatibility claim is made for Claude, Claude Code, OpenCode, or ChatGPT.

## Native OAuth setup prepared (2026-09-28)

Official Inspector 2.8.0 Web documentation specifies `http://localhost:6274/oauth/callback`. That URI was initially added to the existing public test client (`sakai-mcp-dev-test-client`), preserving its existing `http://localhost` URI. The client still requests only the existing delegated `mcp.access` scope; no other client, scope, API permission, or consent grant was added. Inspector's CLI/TUI callback (`http://127.0.0.1:6276/oauth/callback`) was not added because this test uses the Web UI. A later actual Web authorization request used the `127.0.0.1:6274` callback instead; the exact callback correction is recorded below.

## Native OAuth discovery correction (2026-09-29)

The human's first Inspector 2.8.0 Web connection reached Entra but stopped before account selection with `AADSTS9010010`: the requested resource did not match the requested scopes. The unauthenticated MCP `401` and protected-resource discovery `200` were expected. Inspector's OAuth client preferred the server's advertised `scopes_supported: ["mcp.access"]` over the locally configured fully qualified scope, then requested `resource=https://mcp.smartdigest.app` with bare `mcp.access`. Read-only Entra authorization probes with the existing client and callback reproduced the same error for bare `mcp.access offline_access`; the full `https://mcp.smartdigest.app/mcp.access offline_access` scope reached the Microsoft sign-in screen without that parameter error. No user authenticated during these probes.

Commit `9f388f3bda3eb1e98b7756010de2435235915f7a` changed only the protected-resource metadata to advertise `https://mcp.smartdigest.app/mcp.access`, derived from the configured public resource and existing scope name. Inbound JWT authorization still checks the delegated `scp` claim for `mcp.access`. The targeted metadata protocol test and Ruff check passed locally. The [exact-commit MCP deployment](https://github.com/BuriAhmad/sakai-mcp/actions/runs/36524159500) built, scanned, and deployed successfully. Azure reports `ca-mcp-sakai-dev--0000008` as the latest ready revision, with immutable image digest `sha256:ff656a4af5a67447e83605b3f2ec9f1258e51c9e71afb992b879b0095048d6cf`; the previous ready revision was `ca-mcp-sakai-dev--0000007`. The public protected-resource endpoint now returns the fully qualified scope. The release workflow's live health, Bearer challenge, metadata, image, and revision checks passed.

**Native OAuth remains unproved.** The human must reconnect Inspector and complete Entra sign-in. The correction removes the observed authorization-request mismatch; it does not establish an authenticated MCP session, user-specific tools, or a host approval UI.

On the next human-operated Inspector attempt, Student A reached the Microsoft sign-in flow and was then interrupted by a Microsoft Authenticator registration prompt. The human did not complete registration or the OAuth callback. A read-only Graph query returned no Conditional Access policies, while queries for security defaults and authentication-method policy were denied because the current Azure CLI token lacks policy-read permission. A subsequent human-provided Entra admin-center screenshot showed Security defaults enabled at that point. Native OAuth and MCP user tests remain pending. This session did not change that tenant setting.

## Inspector Web callback correction (2026-09-29)

A subsequent human-operated authorization request failed at Entra with `AADSTS50011`. The error named the exact redirect URI `http://127.0.0.1:6274/oauth/callback` for the existing test-client app ID; the registration then contained only `http://localhost:6274/oauth/callback` and `http://localhost`. The exact `127.0.0.1:6274` URI was added to that same public test client. A readback confirmed all three public-client redirects and the unchanged sole delegated MCP `mcp.access` permission. No new client, Graph/API permission, scope, consent grant, or MCP deployment was introduced. The human must retry the native OAuth flow; no successful callback or authenticated Inspector tool call is claimed yet.

Next, the human must perform Inspector's native Entra sign-in and the interactive tests. Inspector's manual Run Tool action is not host approval evidence. For any later real host claiming approval, configure `create_course_announcement` as `Needs approval`; before an approved synthetic create, verify a unique title is absent, make one intentional call, and reconcile its Sakai object ID. Never blindly replay an ambiguous result. Preserve no server-side elicitation and no content-based deduplication.

Client matrix at this checkpoint:

| Client | Connection/auth | Catalog | Read | Write approval | Cancellation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Inspector 2.8.0 CLI via local bearer proxy | Transport only; native OAuth untested | Five tools observed | One successful Student A read after one proxy error | Not applicable as approval host | Not tested | Diagnostic only |
| Claude remote custom connector | Not tested | Not tested | Not tested | Not tested | Not tested | Awaiting client registration and interactive OAuth |
| Claude Code / OpenCode / ChatGPT | Not tested | Not tested | Not tested | Not tested | Not tested | No support claim |

The next Phase 25 step is a native OAuth connection in a selected real host, then the runbook's full read, pre-execution approval, Cancel/no-write, Allow/exactly-one, persistent-allow, and autonomous-mode matrix. Phase 25 must remain unpassed until that evidence exists.
