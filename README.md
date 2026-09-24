# sakai-mcp

Infrastructure, operations, and future MCP services for the Sakai development environment on Azure.

The canonical infrastructure repository is `BuriAhmad/sakai-mcp`. GitHub Actions validates all shell scripts and compiles the Bicep infrastructure template on pushes and pull requests.

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
./sakai source                         # clone Sakai 25.2 locally
./sakai stop                           # stop compute when finished
```

See [VM access](docs/VM_ACCESS.md) for the security model and troubleshooting, and [repository strategy](docs/REPOSITORY_STRATEGY.md) before changing Sakai or adding the MCP service.

## Layout

- `deployment/` — Bicep infrastructure and VM/application configuration
- `scripts/` — guarded operational scripts
- `docs/` — architecture, runbooks, and decisions
- `services/` — project-owned application services (the future MCP belongs here)
- `source/sakai/` — optional local upstream Sakai checkout, ignored by this repository
