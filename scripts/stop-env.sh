#!/usr/bin/env bash
set -Eeuo pipefail
SUBSCRIPTION_ID='55a5701c-411e-45f1-9829-9c80f526d9eb'
RESOURCE_GROUP='rg-sakai-mcp-dev'
VM_NAME='vm-sakai-dev'
MYSQL_NAME='mysql-sakai-dev-55a5701c-uae'
MCP_APP_NAME='ca-mcp-sakai-dev'
[[ "$(az account show --query id -o tsv)" == "$SUBSCRIPTION_ID" ]] || { echo 'Wrong Azure subscription.' >&2; exit 1; }
[[ "$(az group exists -n "$RESOURCE_GROUP")" == 'true' ]] || { echo "Missing resource group $RESOURCE_GROUP." >&2; exit 1; }
MCP_APP_URI="https://management.azure.com/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP/providers/Microsoft.App/containerApps/$MCP_APP_NAME"
mcp_state="$(az rest --method get --uri "$MCP_APP_URI?api-version=2025-07-01" --query properties.runningStatus -o tsv)"
if [[ "$mcp_state" == 'Running' ]]; then
  az rest --method post --uri "$MCP_APP_URI/stop?api-version=2025-07-01" --output none
elif [[ "$mcp_state" != 'Stopped' ]]; then
  echo "MCP app is $mcp_state; wait for a stable state before stopping." >&2
  exit 1
fi
for _ in {1..40}; do
  [[ "$(az rest --method get --uri "$MCP_APP_URI?api-version=2025-07-01" --query properties.runningStatus -o tsv)" == 'Stopped' ]] && break
  sleep 15
done
[[ "$(az rest --method get --uri "$MCP_APP_URI?api-version=2025-07-01" --query properties.runningStatus -o tsv)" == 'Stopped' ]] || { echo 'MCP app did not stop within 10 minutes.' >&2; exit 1; }
FQDN="$(az vm show -d -g "$RESOURCE_GROUP" -n "$VM_NAME" --query fqdns -o tsv 2>/dev/null || true)"
vm_state="$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$VM_NAME" --query "instanceView.statuses[?starts_with(code, 'PowerState/')].code | [0]" -o tsv)"
if [[ "$vm_state" != 'PowerState/deallocated' ]]; then
  if [[ "$vm_state" == 'PowerState/running' && -n "$FQDN" ]]; then
    ssh -o BatchMode=yes -o ConnectTimeout=10 -i "$HOME/.ssh/buriPersonal" sakaiadmin@"$FQDN" 'sudo systemctl stop tomcat' || true
  fi
  az vm deallocate -g "$RESOURCE_GROUP" -n "$VM_NAME" --output none
fi
for _ in {1..60}; do
  [[ "$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$VM_NAME" --query "instanceView.statuses[?starts_with(code, 'PowerState/')].displayStatus | [0]" -o tsv)" == 'VM deallocated' ]] && break
  sleep 15
done
[[ "$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$VM_NAME" --query "instanceView.statuses[?starts_with(code, 'PowerState/')].displayStatus | [0]" -o tsv)" == 'VM deallocated' ]] || { echo 'VM did not deallocate.' >&2; exit 1; }
mysql_state="$(az mysql flexible-server show -g "$RESOURCE_GROUP" -n "$MYSQL_NAME" --query state -o tsv)"
if [[ "$mysql_state" == 'Ready' ]]; then
  az mysql flexible-server stop -g "$RESOURCE_GROUP" -n "$MYSQL_NAME" --output none
elif [[ "$mysql_state" != 'Stopped' ]]; then
  echo "MySQL is $mysql_state; wait for a stable state before stopping." >&2
  exit 1
fi
for _ in {1..60}; do
  [[ "$(az mysql flexible-server show -g "$RESOURCE_GROUP" -n "$MYSQL_NAME" --query state -o tsv)" == 'Stopped' ]] && break
  sleep 15
done
[[ "$(az mysql flexible-server show -g "$RESOURCE_GROUP" -n "$MYSQL_NAME" --query state -o tsv)" == 'Stopped' ]] || { echo 'MySQL did not stop within 15 minutes.' >&2; exit 1; }
VM_STATE="$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$VM_NAME" --query "instanceView.statuses[?starts_with(code, 'PowerState/')].displayStatus | [0]" -o tsv)"
MYSQL_STATE="$(az mysql flexible-server show -g "$RESOURCE_GROUP" -n "$MYSQL_NAME" --query state -o tsv)"
echo "VM state: $VM_STATE"
echo "MySQL state: $MYSQL_STATE"
echo 'MCP app state: Stopped'
echo 'Persistent disks, MySQL storage/backups, public IP, registry, logs, and other resources can still incur charges.'
echo 'MySQL can automatically restart after 30 continuous days stopped. Check ./sakai status periodically.'
