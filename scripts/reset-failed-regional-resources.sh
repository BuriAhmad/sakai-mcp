#!/usr/bin/env bash
set -Eeuo pipefail

# Removes only the named, failed Central India application resources. It preserves
# rg-sakai-mcp-dev, its budget, and all repository/local-secret files.
SUBSCRIPTION_ID='55a5701c-411e-45f1-9829-9c80f526d9eb'
RESOURCE_GROUP='rg-sakai-mcp-dev'
FAILED_REGION='centralindia'

[[ "$(az account show --query id -o tsv)" == "$SUBSCRIPTION_ID" ]] || exit 1
resource_type() {
  case "$1" in
    vm-*) echo 'Microsoft.Compute/virtualMachines' ;;
    nic-*) echo 'Microsoft.Network/networkInterfaces' ;;
    pip-*) echo 'Microsoft.Network/publicIPAddresses' ;;
    vnet-*) echo 'Microsoft.Network/virtualNetworks' ;;
    nsg-*) echo 'Microsoft.Network/networkSecurityGroups' ;;
  esac
}
for resource in vm-sakai-dev nic-sakai-dev pip-sakai-dev vnet-sakai-dev nsg-sakai-app-dev; do
  location="$(az resource show -g "$RESOURCE_GROUP" -n "$resource" --resource-type "$(resource_type "$resource")" --query location -o tsv 2>/dev/null || true)"
  [[ -z "$location" || "$location" == "$FAILED_REGION" ]] || { echo "Refusing to remove $resource in $location." >&2; exit 1; }
done

echo "Removing only failed Central India Sakai resources from $RESOURCE_GROUP; preserving RG and budget."
az resource delete -g "$RESOURCE_GROUP" -n shutdown-computevm-vm-sakai-dev --resource-type Microsoft.DevTestLab/schedules --output none 2>/dev/null || true
az vm delete -g "$RESOURCE_GROUP" -n vm-sakai-dev --yes --output none
az disk delete -g "$RESOURCE_GROUP" -n vm-sakai-dev_OsDisk_1_cdce355493d0437dacbe5d3c344d14ee --yes --output none
az network nic delete -g "$RESOURCE_GROUP" -n nic-sakai-dev --output none
az network public-ip delete -g "$RESOURCE_GROUP" -n pip-sakai-dev --output none
az network private-dns link vnet delete -g "$RESOURCE_GROUP" -z private.mysql.database.azure.com -n vnet-sakai-dev-link --yes --output none
az network private-dns zone delete -g "$RESOURCE_GROUP" -n private.mysql.database.azure.com --yes --output none
az network vnet delete -g "$RESOURCE_GROUP" -n vnet-sakai-dev --output none
az network nsg delete -g "$RESOURCE_GROUP" -n nsg-sakai-app-dev --output none

az resource list -g "$RESOURCE_GROUP" --query '[].{name:name,type:type,location:location}' -o table
