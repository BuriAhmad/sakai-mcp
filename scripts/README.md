# Local operations and validation

Use `./sakai help` from the repository root for supported runtime commands. Existing command and deployment script paths remain stable.

Shared local-operation responsibilities are separated under `lib/`:

- `config.sh`: non-secret resource names and the existing SSH-key override.
- `azure.sh`: local prerequisites, Azure account selection, VM-state guards and resource lookup; explicit login uses the same subscription configuration.
- `ssh.sh`: key validation, public-IP discovery and the explicitly invoked restricted firewall update.

Sourcing these libraries defines configuration/functions; it does not sign in, start resources or change firewall rules. Callers opt into the required operation. Runtime starts, stops, deployment and firewall changes retain the repository's authorization boundaries.

After `uv sync --locked` in `services/mcp/`, run `./scripts/check-mcp.sh` from the repository root for the same lint, format, types, architecture, contracts and tests used by CI. `check-repo-context.sh` verifies service/deployment guidance. `build-mcp-image.sh` remains the image/security validation entrypoint and requires an already available Docker daemon.
