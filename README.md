# sakai-mcp

Sakai application source, Azure infrastructure, operations, and future MCP services in one repository.

The canonical repository is `BuriAhmad/sakai-mcp`. GitHub Actions validates project shell scripts and Bicep infrastructure, and builds Sakai when its source changes. Sakai source is tracked in `apps/sakai/`. These checks do not deploy code to Azure.

## First use on a Mac

Install the Azure CLI and Git, then run:

```bash
./sakai login
./sakai shell
```

`./sakai shell` starts the VM if necessary, detects the Mac network's current public IPv4 address, restricts Azure SSH access to that single address, and connects using the existing SSH key. It never opens SSH to the whole internet.

Useful commands:

```bash
./sakai status                         # inspect the environment
./sakai start                          # start VM + MySQL + application
./sakai shell                          # open a VM terminal
./sakai shell 'cd /opt/sakai-src && git status'
./sakai copy ./file.txt /tmp/file.txt
./sakai stop                           # stop compute when finished
./sakai deploy HEAD --check-only       # verify a pushed Sakai commit
./sakai deploy HEAD                    # build and release it to the dev VM
./sakai rollback RELEASE_ID            # restore the previous Tomcat files
```

See [VM access](docs/VM_ACCESS.md) for the security model, [Sakai releases](docs/SAKAI_RELEASES.md) before deployment, [Sakai source](docs/SAKAI_SOURCE.md) for the imported code, and [repository strategy](docs/REPOSITORY_STRATEGY.md) before adding the MCP service.

## Layout

- `deployment/` — Bicep infrastructure and VM/application configuration
- `scripts/` — guarded operational scripts
- `docs/` — architecture, runbooks, and decisions
- `services/` — project-owned application services (the future MCP belongs here)
- `apps/sakai/` — tracked Sakai application source and project changes
