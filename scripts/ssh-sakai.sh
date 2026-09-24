#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/azure.sh
source "$SCRIPT_DIR/lib/azure.sh"

sakai_require_command ssh
sakai_require_private_key
sakai_open_ssh_for_this_mac
sakai_ensure_vm_running

FQDN="$(sakai_vm_fqdn)"
[[ -n "$FQDN" ]] || sakai_die 'VM has no public FQDN.'

echo "Connecting to $SAKAI_VM_USER@$FQDN..."
exec ssh \
  -o BatchMode=yes \
  -o ConnectTimeout=15 \
  -o ConnectionAttempts=2 \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o StrictHostKeyChecking=accept-new \
  -i "$SAKAI_SSH_KEY" \
  "$SAKAI_VM_USER@$FQDN" "$@"
