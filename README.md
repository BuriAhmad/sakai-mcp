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
./sakai start                          # explicitly start MySQL + VM + application
./sakai shell                          # open a VM terminal
./sakai shell 'cd /opt/sakai-src && git status'
./sakai copy ./file.txt /tmp/file.txt
./sakai stop                           # explicitly stop MySQL + deallocate VM
./sakai deploy HEAD --check-only       # verify a pushed Sakai commit
./sakai deploy HEAD                    # build and release it to the dev VM
./sakai rollback RELEASE_ID            # restore the previous Tomcat files
```

See [VM access](docs/VM_ACCESS.md) for the security model, [Sakai releases](docs/SAKAI_RELEASES.md) before deployment, [Sakai source](docs/SAKAI_SOURCE.md) for the imported code, and [repository strategy](docs/REPOSITORY_STRATEGY.md) before adding the MCP service.

For the budget alert, retained-resource costs, and the exact pause/resume path, see [Pause and resume](docs/PAUSE_AND_RESUME.md). Local edits, commits, pushes, and CI work while Azure compute is paused. Pushes never allocate resources or deploy application code.

## Layout

- `deployment/` — Bicep infrastructure and VM/application configuration
- `scripts/` — guarded operational scripts
- `docs/` — architecture, runbooks, and decisions
- `services/` — project-owned MCP service
- `apps/sakai/` — tracked Sakai application source and project changes
