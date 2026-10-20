# Independent MCP request/session authentication

This is the extracted shared authentication-only JAR, hosted with original custom-endpoint business code. See [development lines](../../../docs/DEVELOPMENT_WORKTREES.md), the local role record, and [preserved detailed source documentation](../../../docs/mcp/development-lines/extracted-auth-readme.md). The preserved document's historical migration paths refer to the mixed recovery source, not this branch's business state.

Production Java source and tests were extracted unchanged. Existing handlers retain native permissions. The original Python business client, public contracts and custom native controllers remain byte-identical to `208d69ac`. New native dependencies/filter registration are isolated in the auth integration commit; feature gates remain false by default. No live configuration was copied or changed.

The Python flow helper is mirrored as reference source under `docs/mcp/development-lines/protocol/`; it is not installed into the original host. The migrated client owns an explicit version pin, not an import across worktrees.

The recorded positive attachment proof fails403 before RequestFilter/AccessServlet and the Python positive harness does not collect under its recorded invocation. Do not repair these as part of organization or present passing ordinary regressions as attachment acceptance. Preserve the mixed recovery branch's dated reports for exact outcomes.
