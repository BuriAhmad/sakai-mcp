#!/usr/bin/env bash
set -Eeuo pipefail
SUBSCRIPTION_ID='55a5701c-411e-45f1-9829-9c80f526d9eb'
RESOURCE_GROUP='rg-sakai-mcp-dev'
VM_NAME='vm-sakai-dev'
MYSQL_NAME='mysql-sakai-dev-55a5701c-uae'
[[ "$(az account show --query id -o tsv)" == "$SUBSCRIPTION_ID" ]] || { echo 'Wrong Azure subscription.' >&2; exit 1; }
[[ "$(az group exists -n "$RESOURCE_GROUP")" == 'true' ]] || { echo "Missing resource group $RESOURCE_GROUP." >&2; exit 1; }
mysql_state="$(az mysql flexible-server show -g "$RESOURCE_GROUP" -n "$MYSQL_NAME" --query state -o tsv)"
if [[ "$mysql_state" == 'Stopped' ]]; then
  az mysql flexible-server start -g "$RESOURCE_GROUP" -n "$MYSQL_NAME" --output none
elif [[ "$mysql_state" != 'Ready' ]]; then
  echo "MySQL is $mysql_state; wait for a stable state before starting." >&2
  exit 1
fi
for _ in {1..60}; do
  [[ "$(az mysql flexible-server show -g "$RESOURCE_GROUP" -n "$MYSQL_NAME" --query state -o tsv)" == 'Ready' ]] && break
  sleep 15
done
[[ "$(az mysql flexible-server show -g "$RESOURCE_GROUP" -n "$MYSQL_NAME" --query state -o tsv)" == 'Ready' ]] || { echo 'MySQL did not become Ready.' >&2; exit 1; }
vm_state="$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$VM_NAME" --query "instanceView.statuses[?starts_with(code, 'PowerState/')].code | [0]" -o tsv)"
if [[ "$vm_state" == 'PowerState/deallocated' || "$vm_state" == 'PowerState/stopped' ]]; then
  az vm start -g "$RESOURCE_GROUP" -n "$VM_NAME" --output none
elif [[ "$vm_state" != 'PowerState/running' ]]; then
  echo "VM is $vm_state; wait for a stable state before starting." >&2
  exit 1
fi
for _ in {1..60}; do
  [[ "$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$VM_NAME" --query "instanceView.statuses[?starts_with(code, 'PowerState/')].displayStatus | [0]" -o tsv)" == 'VM running' ]] && break
  sleep 15
done
[[ "$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$VM_NAME" --query "instanceView.statuses[?starts_with(code, 'PowerState/')].displayStatus | [0]" -o tsv)" == 'VM running' ]] || { echo 'VM did not enter running state.' >&2; exit 1; }
FQDN="$(az vm show -d -g "$RESOURCE_GROUP" -n "$VM_NAME" --query fqdns -o tsv)"
for _ in {1..90}; do
  if curl -fsS --connect-timeout 10 --max-time 30 -o /dev/null "https://$FQDN/portal"; then
    echo "Sakai is healthy: https://$FQDN/portal"
    "$(dirname "$0")/status-env.sh"
    exit 0
  fi
  sleep 20
done
echo "VM and MySQL are running but Sakai did not pass HTTPS health check within 30 minutes: https://$FQDN/portal" >&2
exit 1
