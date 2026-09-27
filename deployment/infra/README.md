# Azure infrastructure

`main.bicep` is the declarative source of truth for the isolated Sakai development environment:

- `10.42.0.0/16` VNet with an application subnet and a delegated MySQL subnet;
- NSG allowing only HTTPS, HTTP redirect, and SSH from the supplied administrator CIDR;
- private MySQL DNS zone and VNet link;
- private Azure MySQL Flexible Server 8.0 (`Standard_B1ms`, no HA, 20 GB storage);
- Ubuntu 24.04 low-cost 8 GiB burstable Sakai VM (currently `Standard_B2ms`; an equivalent B-series choice may be substituted only for regional capacity) with Standard SSD OS disk and static public IP;
- daily VM auto-shutdown at 19:00 Pakistan Standard Time.

It intentionally does not create a NAT gateway, load balancer, public database endpoint, or public Tomcat rule.

Run `scripts/deploy-infra.sh` rather than invoking the template manually. It gets sensitive parameters from `deployment/.env`, which is ignored by Git.

Run `scripts/configure-budget.sh` to create the resource-group-scoped USD 20 monthly budget with 80% actual-cost and 100% forecast alerts.

## MCP runtime templates

`mcp-foundation.bicep` defines only the additional MCP foundation in the same resource group and Korea Central region: Basic ACR (admin account disabled), RBAC Key Vault, a capped 30-day Log Analytics workspace, Container Apps environment, user-assigned identity, and scoped AcrPull/Key Vault Secrets User role assignments. `mcp-app.bicep` defines the MCP Container App against those resources. The two-stage deployment allows identity roles to propagate and the certificate/private key to be loaded into Key Vault before the first app revision. Neither template changes the Sakai VM, database, or VNet. The MCP service calls Sakai's public HTTPS API with a validated downstream bearer token.

The environment explicitly uses `WorkloadProfiles` with the Consumption profile. Azure created an Express environment when the mode was omitted during the first Phase 18 apply; Express rejected the app's Key Vault secret references. Keep the explicit mode when updating the foundation. The selected `2026-03-02-preview` environment API supports this property; the local Bicep 0.47.16 compiler emits BCP081 because its bundled type definitions do not include this API version, so use the Azure what-if and live mode readback as additional checks.

Compile both with `az bicep build --file deployment/infra/mcp-foundation.bicep --stdout >/dev/null` and the equivalent command for `mcp-app.bicep`. Preview the foundation with `az deployment group what-if --resource-group rg-sakai-mcp-dev --template-file deployment/infra/mcp-foundation.bicep` after verifying the selected subscription. The app requires a digest-pinned ACR image, its full source commit and lockfile SHA-256, the public Container App URL, the verified Sakai origin, and non-secret Entra metadata as deployment parameters. Its secrets are Key Vault references to `obo-private-key` and `obo-certificate`, mounted under `/mnt/secrets`; never pass credential values to ARM or Git. Phase 18 owns both applies and the initial image push. The manual MCP workflow's `bootstrap` mode builds, scans, and pushes that first image without an existing app; record its digest and lock SHA-256 for the app preview. Subsequent digest revision releases use the separate [MCP release guide](../../docs/MCP_RELEASES.md). See [Phase 16 evidence](../../docs/evidence/mcp/phase-16-inventory.md) and the [MCP runbook](../../docs/MCP_IMPLEMENTATION_RUNBOOK.md).
