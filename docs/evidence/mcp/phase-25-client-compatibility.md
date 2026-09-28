# Phase 25 — client compatibility and approval (2026-09-28)

Status: **IN PROGRESS / BLOCKED at native OAuth and human approval testing**. No client-side cancellation or approved-write result is claimed. Phases 26 and 27 were tested independently and checkpointed; their server results do not close this client gate.

## Current product facts checked before client claims

- Official [MCP Inspector 2.8.0 release](https://github.com/modelcontextprotocol/inspector/releases) is dated 2026-09-23. Its [CLI reference](https://github.com/modelcontextprotocol/inspector/blob/main/clients/cli/README.md) documents remote Streamable HTTP, modern/legacy era selection, static OAuth client configuration, and interactive callback defaults. It is a diagnostic client, not a model host with per-tool approval UX. The documented web callback is `http://localhost:6274/oauth/callback`; CLI/TUI default to `http://127.0.0.1:6276/oauth/callback`.
- Official [Claude custom connector instructions](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp) dated 2026-08-11 say remote MCP connectors are available for the account tiers listed there and are brokered from Anthropic's cloud. The [current connector permissions guide](https://support.claude.com/en/articles/11176164-use-connectors-to-extend-claude-s-capabilities) describes `Needs approval`, `Always allow`, and `Blocked` per-tool settings. Those are documentation facts, **not** observed Sakai connector behavior. Claude Desktop is available locally, but no Sakai remote connector was registered or authenticated during this phase.
- The [current ChatGPT developer-mode guide](https://help.openai.com/en/articles/12584461-developer-mode-and-mcp-apps-in-chatgpt) describes full MCP/write beta for Business, Enterprise, and Edu, and says write confirmation can depend on permissions/context. This account/workspace configuration was not tested, so ChatGPT compatibility is unclaimed.

## Empirical client diagnostic

The actual published Inspector **2.8.0 CLI** was run with modern 2026-07-28 era against an ephemeral localhost proxy forwarding unchanged MCP bodies/headers to `https://mcp.smartdigest.app/mcp` and injecting a fresh synthetic Student A bearer in memory. `tools/list` exited 0 and returned exactly the fixed five V1 names. A `list_my_courses` call later exited 0 and returned a successful nonempty structured course result. The first attempted read returned a proxy-side HTTP 500, then the retry of this **read-only** operation succeeded; the diagnostic bridge was not counted as an OAuth or reliability acceptance result. The local proxy was stopped afterward. No write was issued by Inspector.

The proxy deliberately bypassed Inspector's own OAuth flow, so this demonstrates only CLI transport/catalog/read behavior with a pre-obtained delegated token. It does **not** establish native client connection/authentication, approval display, Cancel/Reject, Allow/exactly-one create, persistent allow, or autonomous-mode behavior. Inspector is not claimed as an approval-enforcing host. No compatibility claim is made for Claude, Claude Code, OpenCode, or ChatGPT.

## Concrete blocking configuration/action

The existing Entra synthetic test client (`sakai-mcp-dev-test-client`) has only `http://localhost` registered as a public redirect URI. Inspector's exact callback paths and Claude's hosted callback are not registered. A native OAuth host test therefore needs a reviewed client registration/redirect configuration, followed by interactive synthetic-user sign-in and actual Cancel/Allow UI actions. Adding a hosted callback to a client registration changes where authorization codes may be returned and is an explicit security choice; it was not silently made. The project should select a dedicated least-privilege test client or an approved change to the current test client, register only the exact required callbacks, then test the chosen host with `create_course_announcement` set to `Needs approval`. The human must perform any sign-in/approval action that cannot be completed safely by the agent. Before any approved synthetic create, generate a unique title, verify absence, issue one intentional call, and reconcile the resulting Sakai object ID; never blindly replay an ambiguous result. Preserve no server-side elicitation and no content-based deduplication.

Client matrix at this checkpoint:

| Client | Connection/auth | Catalog | Read | Write approval | Cancellation | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Inspector 2.8.0 CLI via local bearer proxy | Transport only; native OAuth untested | Five tools observed | One successful Student A read after one proxy error | Not applicable as approval host | Not tested | Diagnostic only |
| Claude remote custom connector | Not tested | Not tested | Not tested | Not tested | Not tested | Awaiting client registration and interactive OAuth |
| Claude Code / OpenCode / ChatGPT | Not tested | Not tested | Not tested | Not tested | Not tested | No support claim |

The next Phase 25 step is a native OAuth connection in a selected real host, then the runbook's full read, pre-execution approval, Cancel/no-write, Allow/exactly-one, persistent-allow, and autonomous-mode matrix. Phase 25 must remain unpassed until that evidence exists.
