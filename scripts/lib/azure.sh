#!/usr/bin/env bash

# Shared Azure account and resource helpers for the Sakai development environment.
# This file is sourced by scripts; it is not meant to be run directly.

# shellcheck source=scripts/lib/config.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/config.sh"

sakai_die() {
  echo "Error: $*" >&2
  exit 1
}

sakai_require_command() {
  command -v "$1" >/dev/null 2>&1 || sakai_die "Missing required command '$1'."
}

sakai_require_azure_login() {
  sakai_require_command az

  if ! az account show --output none >/dev/null 2>&1; then
    sakai_die "Azure CLI is not logged in. Run './sakai login' first."
  fi

  local selected_subscription
  selected_subscription="$(az account show --query id --output tsv)"
  if [[ "$selected_subscription" != "$SAKAI_SUBSCRIPTION_ID" ]]; then
    echo "Selecting the Sakai Azure subscription..."
    az account set --subscription "$SAKAI_SUBSCRIPTION_ID"
  fi

  selected_subscription="$(az account show --query id --output tsv)"
  [[ "$selected_subscription" == "$SAKAI_SUBSCRIPTION_ID" ]] || \
    sakai_die "Unable to select subscription $SAKAI_SUBSCRIPTION_ID."
}

sakai_require_vm_running() {
  sakai_require_azure_login

  local power_state
  power_state="$(
    az vm get-instance-view \
      --resource-group "$SAKAI_RESOURCE_GROUP" \
      --name "$SAKAI_VM_NAME" \
      --query "instanceView.statuses[?starts_with(code, 'PowerState/')].code | [0]" \
      --output tsv
  )"

  [[ "$power_state" == 'PowerState/running' ]] || \
    sakai_die "$SAKAI_VM_NAME is ${power_state:-unknown}. Run './sakai start' only when you intend to allocate the environment."
}

sakai_vm_fqdn() {
  az vm show \
    --resource-group "$SAKAI_RESOURCE_GROUP" \
    --name "$SAKAI_VM_NAME" \
    --show-details \
    --query fqdns \
    --output tsv
}

sakai_login() {
  sakai_require_command az
  az login
  az account set --subscription "$SAKAI_SUBSCRIPTION_ID"
  az account show --query '{subscription:name,id:id,user:user.name}' --output table
}
