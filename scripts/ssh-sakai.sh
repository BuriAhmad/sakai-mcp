#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/ssh.sh
source "$SCRIPT_DIR/lib/azure.sh"

sakai_require_command ssh
sakai_require_private_key
sakai_require_vm_running
sakai_open_ssh_for_this_mac

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
