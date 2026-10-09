# sakai-mcp

Sakai application source, Azure infrastructure, operations, and future MCP services in one repository.

The canonical repository is `BuriAhmad/sakai-mcp`. GitHub Actions validates project shell scripts and Bicep infrastructure, and builds Sakai when its source changes. Sakai source is tracked in `apps/sakai/`. These checks do not deploy code to Azure.

## First use on a Mac

Install the Azure CLI and Git, then run:

```bash
./sakai login
./sakai status
# When you explicitly want the environment running:
./sakai start
./sakai shell
```

`./sakai shell` requires the VM to be running, detects the Mac network's current public IPv4 address, restricts Azure SSH access to that single address, and connects using the existing SSH key. It never opens SSH to the whole internet or starts Azure compute implicitly.

Useful commands:

```bash
./sakai status                         # inspect the environment
./sakai start                          # explicitly resume MySQL + VM + MCP app
./sakai shell                          # open a VM terminal
./sakai shell 'cd /opt/sakai-src && git status'
./sakai copy ./file.txt /tmp/file.txt
./sakai stop                           # explicitly stop MCP app + MySQL; deallocate VM
./sakai deploy HEAD --check-only       # verify a pushed Sakai commit
./sakai deploy HEAD                    # build and release it to the dev VM
./sakai rollback RELEASE_ID            # restore the previous Tomcat files
```

See [VM access](docs/VM_ACCESS.md) for the security model, [Sakai releases](docs/SAKAI_RELEASES.md) before deployment, [Sakai source](docs/SAKAI_SOURCE.md) for the imported code, and [repository strategy](docs/REPOSITORY_STRATEGY.md) before adding the MCP service.

For programmatic Sakai capabilities and source references, start with the [Sakai integration guide](docs/SAKAI_INTEGRATION_GUIDE.md). It records tested interfaces, limitations and future adapter investigation for MCP tools, automation and dependent agent skills.

The instructor assignment workflow is implemented behind disabled-by-default gates and enabled in the separately authorized development release: see [assignment setup](docs/SAKAI_ASSIGNMENT_SETUP.md), [MCP contracts](docs/mcp/assignment-setup-contracts.json), [repository Skill](skills/sakai-assignment-setup/SKILL.md), and [local validation / remaining release gates](docs/evidence/mcp/assignment-setup-local.md). The default V1 catalog remains five tools; the enabled development deployment exposes eight tools and the Skill is installed in both client profiles. See [release evidence](docs/evidence/mcp/assignment-setup-release.md) for exact versions, verified behavior and remaining acceptance limits.

For the budget alert, retained-resource costs, and the exact pause/resume path, see [Pause and resume](docs/PAUSE_AND_RESUME.md). Local edits, commits, pushes, and CI work while Azure compute is paused. Pushes never allocate resources or deploy application code.

## Layout

- `deployment/` — Bicep infrastructure and VM/application configuration
- `scripts/` — guarded operational scripts
- `docs/` — architecture, runbooks, and decisions
- `services/` — project-owned MCP service
- `skills/` — repository-owned agent Skill definitions (not installed automatically)
- `apps/sakai/` — tracked Sakai application source and project changes
