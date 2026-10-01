#!/usr/bin/env bash

# Shared Azure/SSH settings and helpers for the Sakai development environment.
# This file is sourced by scripts; it is not meant to be run directly.

SAKAI_SUBSCRIPTION_ID='55a5701c-411e-45f1-9829-9c80f526d9eb'
SAKAI_RESOURCE_GROUP='rg-sakai-mcp-dev'
SAKAI_VM_NAME='vm-sakai-dev'
SAKAI_VM_USER='sakaiadmin'
SAKAI_NSG_NAME='nsg-sakai-app-dev'
SAKAI_SSH_RULE_NAME='allow-ssh-admin-only'
SAKAI_SSH_KEY="${SAKAI_SSH_KEY:-$HOME/.ssh/buriPersonal}"

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

sakai_public_ipv4() {
  sakai_require_command curl

  local address octet
  local -a octets
  address="$(curl --fail --silent --show-error --max-time 20 https://api.ipify.org)" || \
    sakai_die 'Unable to determine this Mac public IPv4 address.'

  [[ "$address" != *:* ]] || sakai_die "Expected an IPv4 address, received '$address'."
  IFS='.' read -r -a octets <<< "$address"
  [[ ${#octets[@]} -eq 4 ]] || sakai_die "Invalid public IPv4 address '$address'."
  for octet in "${octets[@]}"; do
    [[ "$octet" =~ ^[0-9]{1,3}$ ]] && ((10#$octet <= 255)) || \
      sakai_die "Invalid public IPv4 address '$address'."
  done

  printf '%s\n' "$address"
}

sakai_open_ssh_for_this_mac() {
  sakai_require_azure_login

  local current_cidr configured_cidr
  current_cidr="$(sakai_public_ipv4)/32"
  configured_cidr="$(
    az network nsg rule show \
      --resource-group "$SAKAI_RESOURCE_GROUP" \
      --nsg-name "$SAKAI_NSG_NAME" \
      --name "$SAKAI_SSH_RULE_NAME" \
      --query sourceAddressPrefix \
      --output tsv
  )" || sakai_die "Could not read the SSH network rule."

  if [[ "$configured_cidr" == "$current_cidr" ]]; then
    echo "SSH firewall rule already allows this Mac's network ($current_cidr)."
    return
  fi

  echo "Updating SSH firewall rule: $configured_cidr -> $current_cidr"
  az network nsg rule update \
    --resource-group "$SAKAI_RESOURCE_GROUP" \
    --nsg-name "$SAKAI_NSG_NAME" \
    --name "$SAKAI_SSH_RULE_NAME" \
    --source-address-prefixes "$current_cidr" \
    --access Allow \
    --output none
  echo 'SSH remains restricted to one public IPv4 address.'
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

sakai_require_private_key() {
  [[ -r "$SAKAI_SSH_KEY" ]] || \
    sakai_die "SSH private key not found at '$SAKAI_SSH_KEY'. See docs/VM_ACCESS.md."
}
