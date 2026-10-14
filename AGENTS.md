# Repository guide

This repository owns the Sakai development environment's Azure infrastructure, operations, and project services. Sakai application source lives under `apps/sakai/`.

## Where to work

- `deployment/` — Bicep and VM/application deployment; follow `deployment/AGENTS.md`.
- `scripts/` and `./sakai` — local operations and the human-facing CLI.
- `services/mcp/` — project-owned Python MCP service, tests, and container source; follow its README and scoped `AGENTS.md`.
- `docs/` — architecture, access instructions, runbooks, and deployment history.
- `skills/` — repository-owned agent Skill definitions; the [assignment setup Skill](skills/sakai-assignment-setup/SKILL.md) has a separately authorized opt-in development release; see [release evidence](docs/evidence/mcp/assignment-setup-release.md).
- `apps/sakai/` — tracked Sakai application source and project changes.

## Sources of truth

- Use the tracked Bicep, scripts, and service code for intended behavior. Use `docs/REPOSITORY_STRATEGY.md` for repository boundaries and `docs/INFRASTRUCTURE.md` for the Azure architecture.
- For the next instructor workflow, read [assignment setup design](docs/SAKAI_ASSIGNMENT_SETUP.md); it defines the opt-in implementation, tool contracts and native services without expanding the default V1 catalog. Its [release evidence](docs/evidence/mcp/assignment-setup-release.md) records deployed checks and remaining acceptance limits.
- For the TA workflow, read [assignment grading design](docs/SAKAI_ASSIGNMENT_GRADING.md): the opt-in native/MCP implementation and approved save/return workflow. The [MCP-only resource migration](docs/SAKAI_GRADING_MCP_RESOURCES.md) replaces the standalone importer with server grading/report tools. Deploy native Sakai first, then the exact-commit MCP revision using the [grading resource release procedure](docs/GRADING_MCP_RESOURCE_RELEASE.md); general release paths are [Sakai](docs/SAKAI_RELEASES.md) and [MCP](docs/MCP_RELEASES.md). See [release evidence](docs/evidence/mcp/assignment-grading-release.md) and [local evidence](docs/evidence/mcp/assignment-grading-local.md).
- Consult [the Sakai integration guide](docs/SAKAI_INTEGRATION_GUIDE.md) before adding Sakai capabilities to MCP, adapters, provisioning scripts, or dependent agent skills; it records verified interfaces, source locations, and remaining gaps.
- For test-data seeding, fixture imports or provisioning, read [Sakai test data seeding](skills/sakai-test-data-seeding/SKILL.md). It routes to the general workflow and assignment-with-submissions recipe, preserves prior mistakes, and explains how to research and document unfamiliar data kinds before treating them as proven recipes.
- Use `docs/VM_ACCESS.md` for SSH access and `docs/Sakai_Deployment_Runbook.md` for deployment procedures. `docs/DEPLOYMENT_STATUS.md` is a dated execution record, not a current-state inventory.
- Use `docs/PAUSE_AND_RESUME.md` for cost, preservation, and exact pause/resume commands. Never start or stop the VM, MySQL, or MCP app, schedule a start, or change MCP capacity merely because an alert arrived or a local edit/push occurred. Runtime state changes require the user's explicit request or permission. Read-only status checks are fine.
- Check changing Azure facts with `./sakai status` or read-only Azure queries. Verify the selected subscription before any Azure change. Do not infer live state from documentation.
- Keep secrets, private keys, database dumps, generated credentials, and uploaded content out of Git. Runtime data and secrets belong in Azure or ignored local files such as `deployment/.env`.

## Take initiative at approval boundaries

When deployment, feature enablement, runtime changes or another approval-required action is an appropriate next step toward the user's intended outcome, proactively prepare and ask for the missing authorization. Do not silently stop at a local implementation or disabled capability when the user expects a usable workflow. First check the conversation for existing authorization and complete the preparation and read-only checks already within scope; do not ask again for an action the user has already authorized.

Make the request concrete: explain what is ready, the proposed action and affected environment, relevant prerequisites or blockers, and material effects such as downtime, cost or student-visible changes. Name the instruction that requires approval. If preparation is blocked, explain the blocker and ask for the specific decision or information needed to proceed. Respect an explicit request to defer or avoid deployment or another action.

This guidance adds initiative to request approval; it does not grant authorization or change deployment, runtime, privacy or academic-record approval requirements.

## Useful commands

- `./sakai help` lists local operations; `./sakai status` reads the current environment.
- Local edits, commits, pushes, and CI work while Azure compute is paused. Pushes do not deploy. `./sakai shell` and `./sakai deploy` require a running VM and must not start one implicitly.
- CI checks Bash syntax, ShellCheck errors, whitespace, tracked secrets, Bicep compilation, repository guidance, and MCP tests, types, and security scans.

## Keep this guide current

When a change adds or moves a service, code location, CLI command, deployment route, or Azure resource, review this guide and the relevant scoped guide and documentation in the same change. Add a short path and pointer only when it helps someone find or safely work on the new area. Put detailed procedures in a README or `docs/`. Add a scoped `AGENTS.md` when an area gains distinct working rules. Remove entries that no longer match the repository.

Run `./scripts/check-repo-context.sh` after changing the `services/` or `deployment/` layout. It detects missing README files and guide entries for their direct child directories; review changes inside existing directories yourself.
