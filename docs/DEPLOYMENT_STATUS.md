# Sakai Azure Sandbox — Deployment Status

This is the chronological execution record for the Sakai 25.2 development sandbox.

## 2026-09-14 — Phase 1: Azure inventory

### Attempted

- Read the complete deployment runbook before making any changes.
- Inspected the Azure CLI authentication context, existing resource groups, and existing VNets/address spaces.
- Identified the administrator's current public IPv4 address for a restricted SSH rule.

### Completed successfully

- Azure CLI 2.90.0 is installed and authenticated.
- Intended subscription confirmed explicitly: `Azure for Students` (`55a5701c-411e-45f1-9829-9c80f526d9eb`), status `Enabled`; signed-in identity is `b.ahmadkhan3@gmail.com`.
- Existing resource-group inventory is empty.
- Existing VNet inventory is empty, so `10.42.0.0/16` is non-overlapping in this subscription.
- Current administrator source IP detected as `39.49.85.3`; it will be used as a `/32` SSH restriction (not committed as a secret).
- Local SSH public keys are available; `~/.ssh/buriPersonal.pub` will be used for VM access.

### Resources created or modified

- None.

### Files added or modified

- Created this execution log.

### Verification performed

- `az version`
- `az account show`
- `az group list`
- `az network vnet list`
- Public-IP lookup from the deployment workstation.

### Failures, blockers, and resolution

- Regional SKU query is taking longer than the initial command timeout. No infrastructure action depends on it yet; it will be rerun with a bounded/targeted query before provisioning.

### Deferred

- Cost budget creation requires a notification contact/amount choice not specified by the runbook. A low-cost tag/SKU plan and VM auto-shutdown will be created; budget creation will be attempted only if the subscription permits a safely configured alert without inventing notification details.

### Current state

- No Azure resource groups or resources exist in the selected subscription.
- The environment has not yet been provisioned.

### Next step

- Create the network, database, and VM through the validated idempotent Bicep template.

## 2026-09-14 — Phase 2: project boundary, names, and cost controls

### Attempted

- Established deterministic resource names, tags, low-cost SKUs, and an idempotent infrastructure template.
- Created the dedicated project resource group and a resource-group-scoped budget with alerts.

### Completed successfully

- Created `rg-sakai-mcp-dev` in `eastus` with the required project tags.
- Verified it initially contains no resources other than its management metadata.
- Created `sakai-dev-monthly-20usd`: USD 20 monthly cost budget for the resource group with 80% actual-cost and 100% forecast alerts sent to the subscription owner.
- Created and Bicep-validated `deployment/infra/main.bicep`; it declares only the agreed VNet/subnets/NSG/private DNS, private MySQL, public-IP VM, and auto-shutdown resources.
- Resolved a local Bicep CLI installation failure by replacing a zero-byte interrupted download with Bicep CLI 0.47.16, then validated the template.

### Resources created or modified

- `rg-sakai-mcp-dev`
- `Microsoft.Consumption/budgets/sakai-dev-monthly-20usd` scoped to that resource group

### Files added or modified

- `.gitignore`
- `deployment/infra/main.bicep`
- `deployment/infra/parameters/dev.bicepparam`
- `deployment/infra/README.md`
- `scripts/deploy-infra.sh`
- `scripts/configure-budget.sh`
- `docs/INFRASTRUCTURE.md`

### Verification performed

- Bicep compilation completed successfully.
- Azure API readback confirms both spending-alert thresholds and the resource group tags.

### Failures, blockers, and resolution

- The installed CLI's budget subcommand did not support notification arguments. Replaced that call with a resource-group-scoped Azure Resource Manager API request in the saved `configure-budget.sh` script.
- Azure requires budget start dates to be the first of a month; corrected the schedule to 2026-09-01 through 2027-09-30 and verified the result.

### Current state

- Dedicated resource group and budget are active. Application/network/database/VM resources are not yet created.

### Next step

- Run the Bicep deployment, inspect every created resource, and validate public outbound plus private MySQL connectivity from the VM.

## 2026-09-14 — Phase 3 attempt: network, private DNS, database, and VM

### Attempted

- Ran the saved idempotent `scripts/deploy-infra.sh` for the agreed East US deployment.

### Completed successfully

- Generated the MySQL administrator password locally in `deployment/.env` with owner-only permissions; it remains ignored by Git.
- Verified after the failure that `rg-sakai-mcp-dev` contains no Azure resources from the unsuccessful deployment.
- Identified the governing subscription policy and its allowed regions.

### Resources created or modified

- No VNet, subnet, DNS, MySQL, VM, NIC, public IP, NSG, or shutdown schedule was created.

### Verification performed

- Resource-group resource listing confirmed the failed deployment left no partial resources.
- Subscription policy `sys.regionrestriction` (`Allowed resource deployment regions`) permits only: `indiasouthcentral`, `centralindia`, `koreacentral`, `malaysiawest`, and `uaenorth`.

### Failures, blockers, and resolution

- **Blocker:** Azure denied every East US resource with `RequestDisallowedByAzure` because East US is forbidden by the subscription's allowed-region policy.
- **Resolution required:** Region is a fixed architectural decision in the runbook. I will not silently replace East US. The user must authorize one allowed replacement region after its VM/MySQL availability is checked. The recommended candidate is Central India because it is geographically closest to the current administrator location and is explicitly permitted, but it has not been selected or used.

### Deferred

- All infrastructure provisioning and application phases are deferred pending explicit region direction.

### Current state

- Only the dedicated resource group and budget exist. No compute or database billing resources exist.

### Next step

- On user approval, set the region consistently in the saved Bicep parameter file, check the agreed SKUs in that permitted region, rerun the same Bicep deployment, and continue with private connectivity verification.

## 2026-09-14 to 2026-09-15 — Phases 3–8: regional deployment, Sakai build, and clean demo initialization

### Attempted

- Reused the same dedicated resource group and Bicep design to deploy only the agreed sandbox architecture in a subscription-permitted region.
- Provisioned private MySQL, the VM, VNet, private DNS, Nginx/HTTPS, and Sakai 25.2; then performed a clean Sakai application-database bootstrap and demo-data initialization.

### Completed successfully

- The final workload deployment is in `koreacentral`. Central India rejected the MySQL provisioning request for this subscription, and UAE North did not have capacity for the approved low-cost B-series VM; Korea Central satisfied the unchanged design and SKUs.
- Created the VNet, app and delegated MySQL subnets, NSG, private DNS zone/link, private-only MySQL Flexible Server, Ubuntu VM, NIC, static public IP/FQDN, and VM auto-shutdown schedule.
- Verified from the VM that the MySQL FQDN resolves to its private `10.42.2.4` address and accepts encrypted private-VNet connections. Azure readback confirms MySQL public access is disabled.
- Installed Temurin 17.0.15, Maven 3.9.16, Tomcat 9.0.121, Nginx, Certbot, and the MySQL Connector/J driver. Built Sakai tag `25.2` successfully (454 Maven modules).
- Configured Nginx as the sole public application listener with a valid Let’s Encrypt certificate and a 25 MB proxy upload allowance. Public HTTPS `/portal` returned HTTP 200 with certificate verification succeeding; public TCP/8080 was refused.
- Recovered SSH after the client’s public address changed. The NSG remains restricted to the new `110.38.37.3/32`, not opened broadly.
- Performed a guarded reset of only the disposable `sakai` application schema, applied the upstream Sakai MySQL DDL, and completed the Sakai demo loaders. Evidence includes `SampleDataLoader.init end`, 550 seeded sites, and 563 seeded realms.

### Resources created or modified

- All final workload resources listed in `INFRASTRUCTURE.md`.
- Boot diagnostics was enabled during VM access recovery. The `VMAccessForLinux` extension (`enablevmaccess`, version 1.5) was also added during diagnosis; it completed successfully and will be removed after final access/persistence verification if no longer needed.
- NSG SSH source was changed from the former administrator address to `110.38.37.3/32` after verification of the workstation’s current public address.

### Files added or modified

- `deployment/configure-vm.sh`, `deployment/configure-sakai.sh`, `deployment/deploy-sakai.sh`, `deployment/configure-nginx.sh`
- `deployment/remediate-temurin17.sh`, `deployment/initialize-sakai-schema.sh`, `deployment/first-start-sakai.sh`, `deployment/finalize-sakai-bootstrap.sh`
- `scripts/ssh-sakai.sh`, `scripts/copy-to-sakai.sh`, `scripts/start-env.sh`, `scripts/stop-env.sh`, `scripts/status-env.sh`, `scripts/destroy-dev.sh`

### Verification performed

- Azure resource, NSG, private-DNS, MySQL-network, VM-state, and budget readback.
- Private TLS MySQL connectivity from the VM.
- Sakai source/tag and Maven build success.
- First successful local portal response (HTTP 200), public HTTPS portal response (HTTP 200, verified TLS), and negative external TCP/8080 test.
- Confirmed `SampleDataLoader.init end`; confirmed 550 sites and 563 realms after the demo seed.

### Failures, blockers, and resolution

- The initial East US attempt was policy-blocked; Central India’s MySQL provisioning and UAE North B-series capacity were also unavailable. The final Korea Central resources are the sole deployed workload set; no duplicate replacement environment was created.
- Initial startup exposed Java module-access and MySQL Connector/J issues. The runtime was pinned to Sakai-tested Temurin 17.0.15, required module opens were set in the reproducible Tomcat configuration, and Connector/J 9.0.0 was placed in Tomcat’s shared classpath.
- A partial first schema initialization caused demo-loader errors. The guarded first-start script now cleanly stops Tomcat, resets only `sakai` after an explicit confirmation variable, applies upstream DDL in continue mode, then starts demo initialization. The final clean run completed.
- The normal post-demo restart is still in progress at this log entry. It is not yet counted as a completed persistence/restart test.

### Deferred

- Built-in Quartz test-site generation, browser login tests, HTTPS upload/download tests, Tomcat-restart/VM-reboot persistence tests, lifecycle-script verification, final removal decision for the recovery extension, and final stop remain to be completed.

### Current state

- Azure VM and MySQL are running. Demo data is populated. `auto.ddl=false` and `-Dsakai.demo=true` has been removed for normal operation; Tomcat is currently completing the first normal restart.

### Next step

- Wait for normal Tomcat startup, run browser-based LMS and upload tests, perform persistence/reproducibility checks, then stop the preserved development environment.

## 2026-09-15 — Phases 9–11: built-in test data and authenticated LMS/resource checks

### Attempted

- Ran Sakai's shipped `SeedSitesAndUsersJob` through its supported guarded auto-run configuration, then ran it a second time with the upstream `site.seed.eid.password=true` option to provide a deterministic generated test-user credential for verification.
- Logged in through the public HTTPS portal as the administrator and as a generated registered user.
- Created four valid small upload fixtures (PDF, PNG, ZIP, and PPTX) and exercised Sakai content storage with the generated user.

### Completed successfully

- The first built-in Quartz job ran from 05:14:05 through 05:16:01 UTC; the second deterministic-password run ran from 05:25:06 through 05:27:05 UTC. Both have explicit `SeedSitesAndUsersJob completed.` log evidence.
- Both temporary properties were removed after each run. The final normal configuration has neither `quartz.seedsites.autorun` nor `site.seed.eid.password` set.
- After the second run, Sakai contains 564 sites, 205 users, 567 content resources, and 565 binary content bodies (before the four upload fixtures).
- Public HTTPS login succeeded for the built-in administrator account and for a newly created registered test user; the latter has a personal workspace and a seeded course-site membership.
- Four fixtures were accepted by Sakai's authenticated built-in direct-upload endpoint and created four distinct BLOB-backed `CONTENT_RESOURCE` records. The authenticated public content URLs returned HTTP 200 with the expected PDF, PNG, ZIP, and PPTX MIME types and sizes.
- The generated user's public Resources UI visibly lists the `instructor-uploads` folder containing the uploads.

### Resources created or modified

- Sakai application data only: ten official test sites and two batches of official generated users/content, plus four small verification resources in the generated user's personal workspace.

### Files added or modified

- `deployment/run-built-in-test-site-job.sh`
- `scripts/create-upload-fixtures.sh`

### Verification performed

- Tomcat `Server startup` evidence and public HTTPS `/portal` HTTP 200 after the test-job startup.
- Browser login verification for administrator and generated user.
- Database verification of the four fixture records and public authenticated retrieval of each file type.
- Fixture validation before upload with `unzip -t` for both ZIP and PPTX.

### Failures, blockers, and resolution

- The browser automation can display Sakai's legacy JavaScript-driven Resources action menu, but its JavaScript form-submit actions do not issue a request (confirmed in Nginx access logs). This is an automation limitation, not an application failure; it also affects opening a folder via that legacy form action.
- Resolution: upload was performed through Sakai's authenticated built-in direct-upload endpoint, then verified in the public Resources UI at folder level and by authenticated public HTTPS retrieval for all four stored objects. No application, proxy, or security configuration was weakened.

### Deferred

- Tomcat-restart and Azure-VM-reboot persistence checks are in progress. Final lifecycle-script verification, final documentation, and the required environment stop remain.

### Current state

- VM and MySQL remain running. A deliberate Tomcat restart has been issued for the persistence check; application startup is still being awaited at the time of this checkpoint.

### Next step

- Confirm the restarted application and four stored resources, reboot the VM and repeat the persistence check, validate the saved operational scripts, then stop (but do not destroy) the sandbox.

## 2026-09-15 — Phases 12–14: persistence and reproducibility verification

### Attempted

- Restarted the actual Tomcat service, waited for a new full Sakai startup, and retested the public portal and all four stored fixture URLs.
- Restarted the actual Azure VM, verified a new VM boot time and the enabled Tomcat service, waited for another full Sakai startup, and repeated the portal/resource checks.
- Ran the saved operational status script and validated the declarative and shell sources.

### Completed successfully

- Tomcat restart: new `Server startup` at 06:37:53 UTC in 479,961 ms; local portal and public HTTPS portal returned HTTP 200 afterward.
- VM reboot: Azure returned `VM running`; VM boot time changed to 06:39:13 UTC; `tomcat.service` is enabled. New `Server startup` completed at 06:47:34 UTC in 485,062 ms; public portal returned HTTP 200 afterward.
- After *both* restart tests, all PDF, PNG, ZIP, and PPTX fixture URLs returned authenticated public HTTPS HTTP 200 and the database retained exactly four matching `CONTENT_RESOURCE` records.
- `scripts/status-env.sh` reported the intended Azure subscription, `vm-sakai-dev` running, MySQL `Ready`, public MySQL access `Disabled`, and public HTTPS HTTP 200.
- `az bicep build --file deployment/infra/main.bicep`, `bash -n` for provisioning/lifecycle/test scripts, and `git diff --check` all completed without errors.
- Marked the saved fixture/bootstrap/test scripts executable where they are meant to be directly run.

### Resources created or modified

- No additional Azure infrastructure. The VM reboot was an intentional lifecycle test only.

### Files added or modified

- Updated `scripts/start-env.sh` and `scripts/status-env.sh` so their HTTPS health checks validate the real certificate rather than use `curl -k`.
- Updated `scripts/stop-env.sh` to verify the expected resource group and print the final VM/MySQL states after stopping.
- Updated both live documentation files through this phase.

### Verification scope and residual manual UI item

- **Verified end-to-end in browser:** public HTTPS portal presentation; administrator and generated registered-user login; authenticated generated-user personal workspace; Resources UI and the uploaded `instructor-uploads` folder visible.
- **Verified through authenticated Sakai endpoint plus browser/UI verification:** the built-in direct-upload endpoint accepted normal PDF/PNG/ZIP/PPTX content; each object was BLOB-persisted, visible at the user’s Resources-folder level, and retrievable from its authenticated public HTTPS content URL before/after both restart tests.
- **Manual UI item:** the browser automation cannot execute Sakai's legacy JavaScript form-submit action used to open that folder or invoke the native file chooser. A human can optionally perform that click-through/file-chooser/download presentation check in a normal browser. It is an automation limitation, not a failed upload, security, storage, TLS, or persistence check; no infrastructure or application workaround was introduced.

### Deferred

- None before the required cost-control stop. `destroy-dev.sh` remains deliberately unrun.

### Current state

- Definition-of-Done technical checks have passed within the approved browser/endpoint verification scope. VM and MySQL are currently running only until the required final stop action.

### Next step

- Run `scripts/stop-env.sh`, verify `VM deallocated` and MySQL `Stopped`, append the final preserved-state result, and do not destroy the resource group.

## 2026-09-15 — Phase 15: final cost-control stop and handoff

### Attempted

- Ran the repository's required `scripts/stop-env.sh` only after all deployment, LMS, resource, TLS, Tomcat-restart, and VM-reboot checks passed.
- Independently read back the Azure resource states after the script completed.

### Completed successfully

- The final rerun of `scripts/stop-env.sh` printed `VM state: VM deallocated` and `MySQL state: Stopped`.
- Independent Azure readback confirms subscription `55a5701c-411e-45f1-9829-9c80f526d9eb`, resource group `rg-sakai-mcp-dev`, **VM deallocated**, and **MySQL Stopped**.
- The static public endpoint allocation is preserved: `sakai-mcp-dev-55a5701c.koreacentral.cloudapp.azure.com` / `52.231.74.79`.
- The resource group and all persistent resources are preserved. `destroy-dev.sh` was not run.

### Resources created or modified

- No resources were created or deleted. The VM was deallocated and the Azure MySQL Flexible Server was stopped; persistent disks, database storage/backups, public IP, DNS, VNet, and configuration remain.

### Files added or modified

- Finalized this chronological log and `docs/INFRASTRUCTURE.md`.
- Corrected `scripts/stop-env.sh` for Azure CLI compatibility: this CLI supports custom/polled VM state rather than `az vm wait --deallocated`; the script now explicitly polls for `VM deallocated` and prints verified final states.

### Verification performed

- Final shell syntax check for all lifecycle scripts and `git diff --check`.
- Azure API readback for VM power state and MySQL state.

### Failures, blockers, and resolution

- First stop-script run used unsupported `az vm wait --deallocated`; the VM deallocation request itself completed, but the script exited before stopping MySQL. The saved script was corrected to poll the documented power-state value.
- A follow-on reporting-line quoting issue did not affect state changes (VM was already deallocated and MySQL stopped), but was corrected. The final idempotent rerun exited successfully and printed both exact states.

### Deferred

- Optional human click-through of the legacy Resources folder/file-chooser UI remains the only manual presentation check, as described in Phase 11. It is not an infrastructure, application, persistence, or security blocker.

### Current state

- **Definition of Done: passed** within the user-approved authenticated endpoint plus public-browser verification scope.
- **Sakai VM: DEALLOCATED. Azure MySQL: STOPPED. Environment: preserved, not destroyed.**

### Next step

- To resume development, run `scripts/start-env.sh` from this repository; it verifies the intended subscription/resource group, starts MySQL then the VM, waits for Sakai HTTPS health, and prints the URL.

## 2026-09-19 — Mac access and repository workflow

### Completed successfully

- Added the root `./sakai` command for Azure login, VM shell, file copy, environment lifecycle, status, and local source checkout.
- Replaced the brittle fixed-address SSH workflow with a guarded refresh of the existing NSG rule to the caller's current public IPv4 `/32`; SSH still requires the installed private key and password login remains disabled.
- Verified the complete path from this Mac: refreshed the rule, started the deallocated VM, connected as `sakaiadmin`, ran a harmless hostname command, and deallocated the VM again.
- Added a repository strategy for a separate local Sakai checkout and future project-owned MCP service.

### Current state

- **Sakai VM: DEALLOCATED.** The access test did not leave VM compute running.
- SSH port 22 remains restricted to one administrator public IPv4 `/32`, not the internet.
- The parent repository is prepared for its private `BuriAhmad/sakai-mcp` GitHub remote with validation CI. Sakai application source remains a separate future fork.
