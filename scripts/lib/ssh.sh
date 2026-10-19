#!/usr/bin/env bash

# SSH key and firewall helpers; callers explicitly choose these operations.
# shellcheck source=scripts/lib/azure.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/azure.sh"

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

sakai_require_private_key() {
  [[ -r "$SAKAI_SSH_KEY" ]] || \
    sakai_die "SSH private key not found at '$SAKAI_SSH_KEY'. See docs/VM_ACCESS.md."
}
