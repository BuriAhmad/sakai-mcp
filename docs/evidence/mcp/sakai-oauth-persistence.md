# Sakai Codex OAuth persistence repair

Date: 9 October 2026 (Asia/Karachi).

The primary Codex CLI 0.159.2 profile initially reported the enabled Sakai server as `Not logged in`. The primary profile had no explicit MCP credential-store setting and no file-backed MCP credential; the separate test profile used `file` and had a Sakai access token with no refresh token. Both configured only the canonical delegated MCP access scope. The live protected-resource metadata advertises that same API scope; no metadata or runtime change was needed.

## Client change and evidence

Both local profiles now set `mcp_oauth_credentials_store = "file"` and request `https://mcp.smartdigest.app/mcp/mcp.access` plus `offline_access`. Existing client IDs, callbacks, endpoint and write approval remain unchanged. Each configuration has a private dated backup. Credentials remain outside Git. The primary credential file has mode 0600.

A fresh primary `codex mcp login sakai` succeeded. Its saved credential contains an access token and a refresh token. Two independent `codex mcp list` processes reported the server enabled with OAuth. A fresh native Codex app-server discovered the five enabled V1 tools and the installed assignment Skill; a read-only `list_my_courses` call using the primary saved token succeeded without recording course content.

A temporary isolated profile copied the grant privately, marked its local access-token expiry as past, and started the native client. Codex refreshed through Entra and persisted a different access token, a future expiry and a refresh token. A second fresh native process reused the refreshed grant successfully. The temporary credential directory was deleted. An initial probe also asserted Skill discovery, which failed because the temporary profile intentionally lacked Skill files; the corrected authentication-only probe passed.

The separate test profile also completed a fresh interactive login, saved a refresh token in a mode-0600 credential file, and reports OAuth in a fresh CLI process. Its fresh native app-server also discovers the five V1 tools and installed assignment Skill. No Entra registrations/grants or server access policy were changed. The original immediate-loss mechanism is not conclusively established: the previous login process/profile and Keychain entry were not available as evidence. The observed missing refresh token would prevent renewal; deterministic file storage removes the current storage ambiguity.

## References and remaining release gate

[Official Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference) documents `mcp_oauth_credentials_store` and per-server `scopes`. [Microsoft scope guidance](https://learn.microsoft.com/en-us/entra/identity-platform/scopes-oidc#the-offline_access-scope) requires explicitly requesting `offline_access` at the v2.0 authorization endpoint to obtain a refresh token. It is an authorization-server scope and need not be added as an API permission in protected-resource metadata for this client fix.

Assignment setup remains separately disabled pending the guarded replay-fix Sakai release and its live acceptance checks. [Assignment release evidence](assignment-setup-release.md) records that gate. The repair commit's full Sakai CI now passed; disk cleanup approval remains pending. Authentication repair does not enable assignment writes or close the outstanding host-control acceptance gates.
