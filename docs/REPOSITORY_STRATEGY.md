# Repository and development strategy

## Sources of truth

Keep three concerns separate:

| Concern | Source of truth | Location |
| --- | --- | --- |
| Azure infrastructure and operations | This `sakai-mcp` Git repository | Mac + private GitHub remote |
| Upstream/custom Sakai application | This `sakai-mcp` Git repository | `apps/sakai/` locally; `/opt/sakai-src` is only a deployed checkout |
| Runtime data and secrets | Azure MySQL/storage and ignored environment files | Azure + `deployment/.env` |

The VM must not be the only place containing code changes. Edit locally, commit locally, push to the Git remote, and deploy a known commit only when requested. These Git steps work with the VM deallocated and MySQL stopped. A push runs CI; it does not allocate Azure compute or deploy a release. See [Pause and resume](PAUSE_AND_RESUME.md). Avoid editing `/opt/sakai-src` directly except for emergency diagnosis; any emergency change should immediately be reproduced as a normal Git commit.

## Local Sakai source

The `apps/sakai/` directory contains the Sakai 25.2 source and project changes directly in this repository. Its baseline is the official commit currently deployed on the VM, `b5b7800f0fcddf9d0db47276a66065189365d905`. The source is imported without a nested `.git` directory.

Edit Sakai here, commit to this repository, and deploy an explicitly selected commit with `./sakai deploy COMMIT` or the manual GitHub release workflow. See `docs/SAKAI_RELEASES.md` for the build, downtime, health check, and rollback procedure. A local source checkout consumes disk space only; it does **not** run Java, Tomcat, MySQL, containers, or Azure resources.

## What should run locally

Start small:

- Keep source, documentation, tests, formatting, and Git operations local.
- Keep the deployed Sakai/Tomcat/MySQL stack on Azure for integration testing.
- Do not require every contributor to run the full Sakai database stack just to edit code.
- Add a documented local container stack only when fast offline integration testing becomes valuable enough to justify its maintenance.

Cloning source is cheap; running duplicate databases and application servers is what consumes CPU, memory, and setup time.

## MCP service

The project-owned MCP service is under `services/mcp/`:

```text
sakai-mcp/
├── deployment/          Azure and deployment definitions
├── docs/                architecture, decisions, and runbooks
├── scripts/             human-friendly operations
├── services/
│   └── mcp/             MCP source, tests, container file
└── apps/
    └── sakai/           tracked Sakai source and project changes
```

Its locked dependencies, tests, non-root container, CI checks, Bicep runtime, managed identity, and Key Vault references are tracked here. The deployed Container App is separate from the Sakai VM. Pushing MCP source does not update its image; use the manual release path in [MCP releases](MCP_RELEASES.md) when requested.

## Git workflow

The canonical Sakai, infrastructure, and MCP repository is the private GitHub repository `BuriAhmad/sakai-mcp`. GitHub Actions validates project shell syntax, runs ShellCheck, checks that local secrets remain untracked, and compiles the Bicep templates.

Use small branches and pull requests for infrastructure and application changes. Protect the main branch when more than one person contributes. Sakai changes will be committed alongside the MCP and infrastructure in this repository. A push validates; it does not automatically release to Azure.

Do not commit private keys, `.env` files, generated credentials, database dumps, build outputs, or user-uploaded Sakai content.
