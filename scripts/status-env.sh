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
FQDN="$(az vm show -d -g "$RESOURCE_GROUP" -n "$VM_NAME" --query fqdns -o tsv)"
printf 'Public HTTPS: '
curl -fsSI --connect-timeout 10 --max-time 20 "https://$FQDN/portal" | head -n 1 || true
