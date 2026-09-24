#!/usr/bin/env bash
set -Eeuo pipefail
SUBSCRIPTION_ID='55a5701c-411e-45f1-9829-9c80f526d9eb'
RESOURCE_GROUP='rg-sakai-mcp-dev'
VM_NAME='vm-sakai-dev'
MYSQL_NAME='mysql-sakai-dev-55a5701c-uae'
[[ "$(az account show --query id -o tsv)" == "$SUBSCRIPTION_ID" ]] || { echo 'Wrong Azure subscription.' >&2; exit 1; }
[[ "$(az group exists -n "$RESOURCE_GROUP")" == 'true' ]] || { echo "Missing resource group $RESOURCE_GROUP." >&2; exit 1; }
FQDN="$(az vm show -d -g "$RESOURCE_GROUP" -n "$VM_NAME" --query fqdns -o tsv 2>/dev/null || true)"
if [[ -n "$FQDN" ]]; then ssh -o BatchMode=yes -o ConnectTimeout=10 -i "$HOME/.ssh/buriPersonal" sakaiadmin@"$FQDN" 'sudo systemctl stop tomcat' || true; fi
az vm deallocate -g "$RESOURCE_GROUP" -n "$VM_NAME" --output none
for _ in {1..60}; do
  [[ "$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$VM_NAME" --query "instanceView.statuses[?starts_with(code, 'PowerState/')].displayStatus | [0]" -o tsv)" == 'VM deallocated' ]] && break
  sleep 15
done
[[ "$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$VM_NAME" --query "instanceView.statuses[?starts_with(code, 'PowerState/')].displayStatus | [0]" -o tsv)" == 'VM deallocated' ]] || { echo 'VM did not deallocate.' >&2; exit 1; }
az mysql flexible-server stop -g "$RESOURCE_GROUP" -n "$MYSQL_NAME" --output none
until [[ "$(az mysql flexible-server show -g "$RESOURCE_GROUP" -n "$MYSQL_NAME" --query state -o tsv)" == 'Stopped' ]]; do sleep 15; done
VM_STATE="$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$VM_NAME" --query "instanceView.statuses[?starts_with(code, 'PowerState/')].displayStatus | [0]" -o tsv)"
MYSQL_STATE="$(az mysql flexible-server show -g "$RESOURCE_GROUP" -n "$MYSQL_NAME" --query state -o tsv)"
echo "VM state: $VM_STATE"
echo "MySQL state: $MYSQL_STATE"
echo 'Persistent disks, MySQL storage/backups, public IP, and other preserved resources may still incur small charges.'
