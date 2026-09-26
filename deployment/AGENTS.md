# Deployment guide

This directory controls Azure resources and the Sakai VM/application setup. Read the relevant section of `docs/Sakai_Deployment_Runbook.md` before changing a deployment path; use `docs/INFRASTRUCTURE.md` for the current intended architecture.

- `deployment/infra/` contains the Bicep template and parameters. Its README explains deployment inputs.
- `deployment/README.md` distinguishes original bootstrap from the guarded Sakai release path; follow `docs/SAKAI_RELEASES.md` for deploy and rollback.
- Keep the database private, keep SSH limited to the administrator's current `/32` address, and do not expose Tomcat directly. Preserve the resource-group boundary and cost controls unless a task explicitly changes them.
- Keep Tomcat's HTTP connector bound to loopback and its forwarded-scheme trust limited to local Nginx. `configure-tomcat-proxy.sh` owns this repeatable setting; verify an HTTPS Sakai form action after proxy changes.
- Keep Sakai's Java module options aligned with its tracked 25.2 Docker runtime. `ensure-sakai-java-opens.sh` amends the VM's `setenv.sh`; verify the affected tool after restart.
- `configure-mcp-sakai.sh` owns the optional, default-disabled MCP properties in Sakai `local.properties`. Feed it only verified non-secret Entra metadata; use the guarded exact-commit release for the Tomcat restart and preserve its configuration backup.
- Check the Azure subscription and affected resource scope before running a deployment or changing live resources. `./sakai status` is a read-only starting point.
- Never commit `deployment/.env`, credentials, keys, or database content. Deployment scripts should remain repeatable and should fail clearly when required inputs are missing.
- When adding a new deployment directory or pathway, document its purpose and command in that directory's README, then add a pointer here. When changing Azure resources, update the architecture documentation and any affected runbook steps.
