# Repository guide

This repository owns the Sakai development environment's Azure infrastructure, operations, and project services. Sakai application source lives under `apps/sakai/`.

## Where to work

- `deployment/` — Bicep and VM/application deployment; follow `deployment/AGENTS.md`.
- `scripts/` and `./sakai` — local operations and the human-facing CLI.
- `services/mcp/` — reserved for the project-owned MCP service; see its README. It has no implementation yet.
- `docs/` — architecture, access instructions, runbooks, and deployment history.
- `apps/sakai/` — tracked Sakai application source and project changes.

## Sources of truth

- Use the tracked Bicep, scripts, and service code for intended behavior. Use `docs/REPOSITORY_STRATEGY.md` for repository boundaries and `docs/INFRASTRUCTURE.md` for the Azure architecture.
- Use `docs/VM_ACCESS.md` for SSH access and `docs/Sakai_Deployment_Runbook.md` for deployment procedures. `docs/DEPLOYMENT_STATUS.md` is a dated execution record, not a current-state inventory.
- Check changing Azure facts with `./sakai status` or read-only Azure queries. Verify the selected subscription before any Azure change. Do not infer live state from documentation.
- Keep secrets, private keys, database dumps, generated credentials, and uploaded content out of Git. Runtime data and secrets belong in Azure or ignored local files such as `deployment/.env`.

## Useful commands

- `./sakai help` lists local operations; `./sakai status` reads the current environment.
- CI checks Bash syntax, ShellCheck errors, whitespace, tracked secrets, Bicep compilation, and repository guidance coverage.

## Keep this guide current

When a change adds or moves a service, code location, CLI command, deployment route, or Azure resource, review this guide and the relevant scoped guide and documentation in the same change. Add a short path and pointer only when it helps someone find or safely work on the new area. Put detailed procedures in a README or `docs/`. Add a scoped `AGENTS.md` when an area gains distinct working rules. Remove entries that no longer match the repository.

Run `./scripts/check-repo-context.sh` after changing the `services/` or `deployment/` layout. It detects missing README files and guide entries for their direct child directories; review changes inside existing directories yourself.
