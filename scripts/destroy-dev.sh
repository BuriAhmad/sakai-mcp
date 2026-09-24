#!/usr/bin/env bash
set -Eeuo pipefail
SUBSCRIPTION_ID='55a5701c-411e-45f1-9829-9c80f526d9eb'
RESOURCE_GROUP='rg-sakai-mcp-dev'
[[ "$(az account show --query id -o tsv)" == "$SUBSCRIPTION_ID" ]] || { echo 'Wrong Azure subscription.' >&2; exit 1; }
az account show --query '{subscription:name,id:id}' -o table
az group show -n "$RESOURCE_GROUP" --query '{resourceGroup:name,tags:tags}' -o json
read -r -p "Type DELETE $RESOURCE_GROUP to permanently remove only this Sakai environment: " CONFIRM
[[ "$CONFIRM" == "DELETE $RESOURCE_GROUP" ]] || { echo 'Cancelled.'; exit 0; }
az group delete -n "$RESOURCE_GROUP" --yes --no-wait
echo "Deletion submitted for $RESOURCE_GROUP."
