# Pause and resume the development environment

This is the operating guide for preserving the current Sakai installation while limiting compute charges. `./sakai start` and `./sakai stop` are the normal commands that intentionally change VM, MySQL, and MCP Container App runtime state. Run them only when you explicitly choose to. Agents must not run them from a cost alert, status request, code edit, push, or routine test without your request or permission. Do not create a schedule that starts these services without a separate request.

## What the budget alert means

The 2026-10-01 Azure email forecasts **$22.62** for October against the resource-group budget `sakai-dev-monthly-20usd` of **$20**. A forecast is not an actual bill, and the budget is an alert, not a spending cap. Check actual cost by resource and meter in Azure Cost Management before attributing it to one resource. Verify the selected subscription is `55a5701c-411e-45f1-9829-9c80f526d9eb` and the group is `rg-sakai-mcp-dev`.

Azure references: [budget behavior](https://learn.microsoft.com/en-us/azure/cost-management-billing/costs/tutorial-acm-create-budgets), [VM deallocation](https://learn.microsoft.com/en-us/rest/api/compute/virtual-machines/deallocate), [MySQL stop/start and 30-day restart](https://learn.microsoft.com/en-us/azure/mysql/flexible-server/how-to-stop-start-server-portal), [Container App stop](https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/container-apps/stop?view=rest-resource-manager-containerapps-2025-07-01), [Container App start](https://learn.microsoft.com/en-us/rest/api/resource-manager/containerapps/container-apps/start?view=rest-resource-manager-containerapps-2025-07-01), and [Container Apps billing](https://learn.microsoft.com/en-us/azure/container-apps/billing).

The 2026-10-01 read-only check found `vm-sakai-dev` **deallocated**, MySQL **Ready**, and `ca-mcp-sakai-dev` configured for **0–2 replicas**. This is a dated observation, not a promise about the current state. `./sakai status` rechecks it.

Later on 2026-10-01, at the owner's request, the MCP app was stopped through Azure's Container Apps stop API and `./sakai stop` stopped MySQL while keeping the VM deallocated. A read-only status check then reported **MCP Stopped**, **MySQL Stopped**, and **VM deallocated**. The revised `./sakai stop` command repeated successfully in that state. This is an execution record; inspect live state before acting.

## Preserved and still billed

`./sakai stop` stops the MCP Container App, gracefully stops Tomcat when SSH is available, deallocates the VM, and stops MySQL. It does **not** delete or recreate the VM, OS disk, installed software, Sakai releases, MySQL data, backups, static public IP/FQDN, network, DNS, TLS configuration, MCP Container App, registry, Key Vault, Log Analytics workspace, or Entra configuration. A stopped MCP app cannot wake from incoming traffic. Azure may still charge for retained disk, MySQL storage/backups, public IP, ACR Basic, and existing Log Analytics retention. Check actual meters in Cost Management; this preserved deployment cannot guarantee a zero bill.

Azure automatically starts a stopped MySQL Flexible Server after **30 continuous days**, which resumes compute charges. `./sakai status` should be checked periodically during a long pause. VM auto-shutdown at 19:00 Pakistan time affects the VM only and does not stop MySQL; it also does not replace `./sakai stop` for a full pause.

## Pause

From this checkout, with Azure CLI signed in to the project subscription:

```bash
./sakai status
./sakai stop
./sakai status
```

The stop command is repeatable. It verifies `MCP Stopped`, `VM deallocated`, and `MySQL Stopped` before reporting success. If it fails partway through, inspect `./sakai status` and retry once the resource reaches a stable state. Do not destroy the resource group to pause it.

## Work while paused

Edit source and docs locally, run local checks, commit, and push to `origin` as usual. Git and GitHub do not depend on VM or MySQL allocation. A push runs CI but does **not** deploy Sakai or MCP to Azure. The deployed services keep their previous code until an explicitly requested release. `./sakai deploy`, `./sakai shell`, `./sakai copy`, and VM rollback require the VM running and do not start it implicitly. See [repository strategy](REPOSITORY_STRATEGY.md), [Sakai releases](SAKAI_RELEASES.md), and [MCP releases](MCP_RELEASES.md). An MCP image check can run locally or in its manual GitHub workflow while Sakai is paused, but live end-to-end checks need Sakai available.

## Resume exactly the preserved installation

```bash
./sakai status
./sakai start
./sakai status
```

`./sakai start` starts MySQL first, waits for `Ready`, starts the existing VM, waits for `https://<VM FQDN>/portal` to respond, then starts the MCP Container App. Tomcat is enabled as a systemd service on that VM. A full Sakai startup can take several minutes. The script does not redeploy or migrate data. If health checks fail, leave the resources in their reported state and inspect [VM access](VM_ACCESS.md) and the [deployment runbook](Sakai_Deployment_Runbook.md); do not recreate resources or rotate credentials as a first response. The static public IP and FQDN are preserved by this pause path, but verify the actual endpoint and certificate after resuming.

When the work is finished, run `./sakai stop` only on explicit request. For a longer pause, the 30-day MySQL auto-start rule and persistent costs require periodic review. Deleting resources is a separate destructive decision requiring a data export and recovery plan.
