#!/usr/bin/env bash
set -Eeuo pipefail
SUBSCRIPTION_ID='55a5701c-411e-45f1-9829-9c80f526d9eb'
RESOURCE_GROUP='rg-sakai-mcp-dev'
VM_NAME='vm-sakai-dev'
MYSQL_NAME='mysql-sakai-dev-55a5701c-uae'
[[ "$(az account show --query id -o tsv)" == "$SUBSCRIPTION_ID" ]] || { echo 'Wrong Azure subscription.' >&2; exit 1; }
az account show --query '{subscription:name,id:id}' -o table
az vm show -d -g "$RESOURCE_GROUP" -n "$VM_NAME" --query '{vm:name,powerState:powerState,fqdn:fqdns,publicIp:publicIps,privateIp:privateIps}' -o table
az mysql flexible-server show -g "$RESOURCE_GROUP" -n "$MYSQL_NAME" --query '{mysql:name,state:state,fqdn:fullyQualifiedDomainName,publicAccess:network.publicNetworkAccess}' -o table
az containerapp show -g "$RESOURCE_GROUP" -n ca-mcp-sakai-dev --query '{mcp:name,state:properties.provisioningState,minReplicas:properties.template.scale.minReplicas,maxReplicas:properties.template.scale.maxReplicas}' -o table
echo 'Preserved resources (including billable storage/registry/public IP/logs):'
az resource list -g "$RESOURCE_GROUP" --query '[].[name,type]' -o table
VM_STATE="$(az vm get-instance-view -g "$RESOURCE_GROUP" -n "$VM_NAME" --query "instanceView.statuses[?starts_with(code, 'PowerState/')].code | [0]" -o tsv)"
if [[ "$VM_STATE" == 'PowerState/running' ]]; then
  FQDN="$(az vm show -d -g "$RESOURCE_GROUP" -n "$VM_NAME" --query fqdns -o tsv)"
  printf 'Public HTTPS: '
  curl -fsSI --connect-timeout 10 --max-time 20 "https://$FQDN/portal" | head -n 1 || true
else
  echo "Public HTTPS: skipped (VM $VM_STATE)"
fi
