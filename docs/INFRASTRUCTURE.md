# Sakai Azure Sandbox — Infrastructure

This document describes the actual deployed architecture. It is updated as resources are created.

## Confirmed deployment context

| Item | Value |
| --- | --- |
| Subscription | Azure for Students (`55a5701c-411e-45f1-9829-9c80f526d9eb`) |
| Region | Korea Central — Central India denied MySQL provisioning and UAE North had no B-series capacity |
| Resource group | `rg-sakai-mcp-dev` (resource-group metadata location: East US; workload resources: Korea Central) |
| Project tags | `project=sakai-mcp`, `environment=dev`, `purpose=lms-sandbox`, `owner=burhan`, `managed-by=bicep` |
| VNet CIDR | `10.42.0.0/16`, verified non-overlapping with existing subscription VNets |
| SSH access | One administrator public IPv4 `/32`, refreshed by `./sakai shell` |

## Azure resources

- VNet: `vnet-sakai-dev`, `10.42.0.0/16`.
- Application subnet: `snet-sakai-app-dev`, `10.42.1.0/24`, associated with `nsg-sakai-app-dev`.
- MySQL subnet: `snet-sakai-mysql-dev`, `10.42.2.0/24`, delegated exclusively to `Microsoft.DBforMySQL/flexibleServers`.
- Reserved address plan (not created): `10.42.3.0/24` for future MCP/Container Apps; `10.42.4.0/24` for future private services.
- NSG inbound rules: HTTPS 443 from Internet (priority 100), HTTP 80 from Internet for redirect/ACME (110), SSH 22 from one dynamically refreshed administrator `/32` (120). No public 8080 or 3306 rule exists.
- VM: `vm-sakai-dev`, Ubuntu 24.04 LTS, `Standard_B2as_v2` (2 vCPU/8 GiB), 64 GB Standard SSD OS disk, NIC `nic-sakai-dev`, private IP `10.42.1.4`; boot diagnostics enabled and no VM access extension installed.
- Public endpoint: static `pip-sakai-dev`, `52.231.74.79`, `sakai-mcp-dev-55a5701c.koreacentral.cloudapp.azure.com`.
- Auto-shutdown: `shutdown-computevm-vm-sakai-dev`, 19:00 Pakistan Standard Time.
- Private DNS: `private.mysql.database.azure.com` with `vnet-sakai-dev-link`.
- MySQL: `mysql-sakai-dev-55a5701c-uae` (the `-uae` suffix is a deliberate reservation workaround; actual location is Korea Central), MySQL 8.0.21, `Standard_B1ms` burstable, 20 GB Premium_LRS, 360 IOPS, 7-day locally redundant backup, no HA, public access disabled.
- Budget: `sakai-dev-monthly-20usd`, USD 20/month at resource-group scope, 80% actual and 100% forecast email alerts.

## Planned architecture

```text
Internet
  |  HTTPS 443 (and HTTP 80 redirect)
  v
Public IP / NIC — snet-sakai-app-dev (10.42.1.0/24)
  |  Nginx TLS reverse proxy
  v
Sakai VM — Nginx / Tomcat 9 / Sakai 25.2 (Tomcat localhost:8080 only)
  |  private VNet + private DNS
  v
Azure Database for MySQL Flexible Server 8.0
snet-sakai-mysql-dev (10.42.2.0/24, delegated)
```

Reserved-but-uncreated address ranges are `10.42.3.0/24` (future MCP/Container Apps) and `10.42.4.0/24` (future private services).

## Application layout and operations

- Java: Eclipse Temurin 17.0.15+6 at `/opt/temurin17` (the Sakai 25 QA-tested runtime); Maven: 3.9.16; Tomcat: upstream 9.0.121 at `/opt/tomcat`.
- Sakai source: tracked locally at `apps/sakai/` from tag `25.2`, commit `b5b7800f0fcddf9d0db47276a66065189365d905`. The initial VM checkout is `/opt/sakai-src` at that upstream commit. Later releases build exact repository commits under `/opt/sakai-releases/RELEASE_ID/source`; `/opt/sakai-releases/current` records the deployed release. The first verified release is `20260924T181142Z-e0553fef88a0` at commit `e0553fef88a0ca149be3a33f0cd026aec88e9f16`, with Sakai source unchanged from the imported 25.2 baseline. See `docs/SAKAI_RELEASES.md`.
- Runtime properties: `/opt/tomcat/sakai/local.properties`, owner `tomcat:tomcat`, mode `0640`; passwords are not committed.
- Tomcat service: `/etc/systemd/system/tomcat.service`, enabled for boot recovery. Its module-open options follow the tracked Sakai 25.2 Docker `setenv.sh` through `deployment/ensure-sakai-java-opens.sh`; this includes `java.time` for assignment/Gradebook Ignite caching. `auto.ddl=false` and the one-time `-Dsakai.demo=true` flag have been removed after the completed demo seed.
- Nginx is the only public application listener. It forwards to Tomcat on `127.0.0.1:8080`, sets forwarded HTTPS headers, and uses `client_max_body_size 25M`. Tomcat's HTTP connector binds to loopback. Its `RemoteIpValve` trusts forwarded scheme information only from local Nginx, so Sakai generates HTTPS form actions and secure request semantics. `deployment/configure-tomcat-proxy.sh` owns this repeatable VM configuration.
- Let’s Encrypt HTTPS is active for the Azure FQDN; certificate expiry is 2026-12-13 and Certbot renewal is scheduled.
- Sakai content storage: database BLOBs. Sakai 25.2 default `bodyPath` and `bodyVolumes` are intentionally unset. Upload settings are left at the exact 20 MB Sakai defaults; proxy allowance is 25 MB.
- The root `./sakai` command provides login, shell, copy, start, stop, status, deploy, and rollback workflows. `./sakai shell` refreshes the single-address SSH rule before connecting. The destroy script requires the exact `DELETE rg-sakai-mcp-dev` confirmation and is not run by deployment automation.
- `./sakai deploy COMMIT` and `./sakai rollback RELEASE_ID` are the explicit code-only release path. A manual GitHub Actions workflow uses a federated Azure identity scoped to this resource group/VM/NSG and a separate VM SSH key; it restores the previous SSH `/32` after the job. Database migrations and runtime-secret changes are outside this release path.
- Boot diagnostics is enabled. The temporary `VMAccessForLinux` recovery extension was removed after access recovery; no VM access extension remains installed.
- Test/demo content: the official Sakai `SeedSitesAndUsersJob` was executed twice through the guarded `deployment/run-built-in-test-site-job.sh` wrapper. The second run used the upstream deterministic test-password option solely for verification, and both temporary properties were removed automatically afterward. Four small upload fixtures (PDF, PNG, ZIP, and PPTX) were stored in a generated user's personal Resources area using Sakai's authenticated built-in direct-upload endpoint; `CONTENT_RESOURCE_BODY_BINARY` is the confirmed content backend.

## Verified operational behavior

- The official Quartz test job completion and clean normal application start are logged. After both test-job runs the database contained 564 sites, 205 users, 567 resources, and 565 BLOB bodies before the four explicit upload fixtures.
- Public HTTPS portal login was verified for the built-in administrator and a generated registered user. Generated test credentials are not stored in the repository.
- All four fixture types were accepted by Sakai, recorded as four `CONTENT_RESOURCE` entries, and retrieved with expected content types over authenticated public HTTPS. They survived both a Tomcat restart and an Azure VM reboot.
- A full Tomcat restart takes roughly eight minutes because the upstream deployment contains a large set of Sakai WARs; a running systemd unit alone is not an application-ready signal. Operations wait for `Server startup` and a public `/portal` HTTP 200.
- `scripts/status-env.sh` was run against the live environment and reported public HTTPS HTTP 200, MySQL `Ready` with public access disabled, and VM `running`. `scripts/start-env.sh` and `scripts/stop-env.sh` are idempotent guards for this exact subscription/resource group; Bicep and shell syntax validation passed. `destroy-dev.sh` is intentionally not run and requires an exact typed resource-group confirmation.

## Browser automation note

The public browser test verified login, workspace, Resources UI, and visibility of the upload folder. This browser automation cannot execute Sakai's legacy JavaScript form-submit control used for the folder/file-chooser click-through. Upload and download behavior was therefore verified through Sakai's authenticated built-in direct-upload/content endpoints, with the resulting folder visible in the public UI. A normal human browser may optionally exercise that legacy UI control; this does not indicate an Azure, TLS, content-storage, authorization, or application persistence defect.

## Final preserved state (2026-09-15)

- `scripts/stop-env.sh` was run after all verification. It targets only this subscription and `rg-sakai-mcp-dev`, performs a best-effort clean Tomcat stop, deallocates the VM, stops MySQL, and prints verified state values.
- Azure API readback confirms **`vm-sakai-dev` = `VM deallocated`** and **`mysql-sakai-dev-55a5701c-uae` = `Stopped`**. The public IP/FQDN, disk, MySQL storage/backups, VNet, private DNS, NSG, and resource group remain preserved; those persistent resources can still incur small charges.
- Resume with `scripts/start-env.sh`; inspect with `scripts/status-env.sh`; stop again with `scripts/stop-env.sh`. `scripts/destroy-dev.sh` requires the exact `DELETE rg-sakai-mcp-dev` confirmation and was deliberately not run.
- Azure CLI compatibility note: `stop-env.sh` polls the VM power state for `VM deallocated` rather than relying on an unavailable `az vm wait --deallocated` flag. This is the current reproducible source of truth.

## Latest verified state (2026-09-24)

After the code-only baseline release was built and verified over public HTTPS, Tomcat was stopped cleanly and `vm-sakai-dev` was returned to **VM deallocated**. MySQL was **Ready** before and after the release work. The NSG SSH rule remained a single administrator `/32`; the GitHub check-only job restored that rule after using its temporary runner address. The release's rollback files remain on the VM. See the dated entry in `docs/DEPLOYMENT_STATUS.md` for what was exercised and what was not.

## Latest verified state (2026-09-27)

The development VM now runs the Sakai MCP customization at exact commit `d97ce2f7ee45734b95526017ccad0c429c0a9a22` in healthy release `20260927T075226Z-d97ce2f7ee45`. The VM is running, MySQL is Ready, Tomcat is active, and local plus public HTTPS `/portal` checks passed. The current release retains the prior application directories for `./sakai rollback 20260927T075226Z-d97ce2f7ee45`. Earlier GitHub deployment and manual rollback were exercised on 2026-09-25. Check live state with `./sakai status`; this dated paragraph is an execution record. See `docs/DEPLOYMENT_STATUS.md` and `docs/SAKAI_RELEASES.md`.

No credentials or generated secrets are stored in this repository; local deployment secrets are in ignored `deployment/.env` (mode 600).

## MCP integration development rollout (2026-09-27)

The tracked WebAPI tree contains the path-scoped `/api/mcp/v1/*` bearer adapter and five fixed V1 Sakai routes. The adapter is default-disabled in source, and the development VM now enables it through the marked, runtime-only property block owned by [`configure-mcp-sakai.sh`](../deployment/configure-mcp-sakai.sh). The exact-commit build and guarded release passed; public delegated and ordinary-login smoke tests passed as recorded in [`evidence/mcp/phase-8-release.md`](evidence/mcp/phase-8-release.md). A separate MCP resource and Sakai API resource, a development client, delegated OBO grants, a public certificate, and synthetic directory users exist in the selected Entra tenant. The OBO private key and generated test-user credentials remain in ignored local files pending Key Vault/runtime placement. The reserved MCP network/subnet resources above remain uncreated.

## Provisioning blocker

The subscription policy `sys.regionrestriction` denied East US. Central India then denied MySQL provisioning for this subscription, and UAE North had no capacity for the approved low-cost 8 GiB B-series SKUs. The actual successful deployment region is Korea Central. The resource group predates that resolution and therefore retains East US as immutable metadata; all workload resources are co-located in Korea Central.
