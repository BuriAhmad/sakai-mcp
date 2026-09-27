# Phase 16 — MCP Azure inventory and infrastructure preview (2026-09-27)

Status: **PASS for the Phase 16 gate; inventory, local Bicep build, and foundation what-if PASS; apply NOT RUN**.

`git status --short --branch` was clean on `main` before this milestone. `deployment/infra/` initially contained only `main.bicep`, `parameters/dev.bicepparam`, and its README. The selected subscription matched the repository's Azure for Students subscription. Read-only `az resource list -g rg-sakai-mcp-dev` returned Sakai networking, VM, private MySQL, DNS, and shutdown resources only. No MCP runtime foundation resources appeared. Resource-group metadata is East US; existing workloads are in Korea Central.

| Resource or route | Decision | Reason |
| --- | --- | --- |
| `rg-sakai-mcp-dev`, tags, Korea Central workload location | Reuse | Existing sandbox boundary and budget. |
| Sakai public HTTPS origin and `/api/mcp/v1/*` | Reuse | Phase 8 verified delegated bearer protection and ordinary browser behavior. Container Apps can call it over public HTTPS. |
| Sakai VNet/subnets | Leave as-is | MCP does not connect to private MySQL or Tomcat; no required VNet integration. |
| ACR Basic | Add | No registry exists; private immutable service images with admin account disabled. |
| RBAC Key Vault Standard | Add | No vault exists; store the OBO private key and certificate outside source and image. |
| Log Analytics workspace | Add | No workspace exists; Container Apps stdout/stderr sink, 30-day retention and 1 GB daily cap. |
| Container Apps environment | Add | No suitable environment exists; attach to the new log workspace. |
| User-assigned identity | Add | Scoped AcrPull and Key Vault Secrets User, with the identity unavailable to service code. |
| MCP Container App | Add in app template | External HTTPS on one port, zero-to-two replicas with HTTP rule, no affinity, health probes, single revision mode and three inactive revisions retained. |
| Alerting | Extend in later observability phase | Existing USD 20 resource-group budget alerts apply; workload telemetry alerts need a deployed service baseline. |

The templates are `deployment/infra/mcp-foundation.bicep` and `mcp-app.bicep`; both pass `az bicep build --stdout` with Bicep 0.47.16. The foundation and application are separate so the RBAC role assignment can propagate, the private image can be built, and Key Vault secrets can be placed before the app's first revision. The app template requires a digest image reference and verified non-secret endpoint/Entra parameters; no credentials are encoded in it.

Azure `az deployment group what-if --resource-group rg-sakai-mcp-dev --template-file deployment/infra/mcp-foundation.bicep` completed successfully. Its summary is **seven creates and ten ignored existing Sakai resources; zero updates and zero deletes**. The creates are ACR, Key Vault, Log Analytics, Container Apps environment, user-assigned identity, and two resource-scoped role assignments. It masked the generated Log Analytics shared key. The app what-if is **NOT RUN** because its foundation references and image digest do not yet exist; Phase 18 will preview it before app apply. No MCP resources were applied in Phase 16. Azure provider registrations were started as no-cost prerequisites for later deployment.

Schema and security checks used the versioned [Container Apps 2025-07-01 resource reference](https://learn.microsoft.com/en-us/azure/templates/microsoft.app/2025-07-01/containerapps), [managed environment 2025-07-01 reference](https://learn.microsoft.com/en-us/azure/templates/microsoft.app/2025-07-01/managedenvironments), [Key Vault 2024-11-01 reference](https://learn.microsoft.com/en-us/azure/templates/microsoft.keyvault/2024-11-01/vaults), [ACR 2023-07-01 reference](https://learn.microsoft.com/en-us/azure/templates/microsoft.containerregistry/2023-07-01/registries), and [Container Apps secret reference/volume guidance](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets). These references support user-assigned image pull, Key Vault references, and secret file mounts; live runtime verification is pending deployment.
