#!/usr/bin/env bash
set -Eeuo pipefail

[[ $# -eq 2 ]] || { echo "Usage: $0 LOCAL_FILE REMOTE_PATH" >&2; exit 2; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/azure.sh
source "$SCRIPT_DIR/lib/azure.sh"

sakai_require_command scp
sakai_require_private_key
[[ -e "$1" ]] || sakai_die "Local path does not exist: $1"
sakai_open_ssh_for_this_mac
sakai_ensure_vm_running

FQDN="$(sakai_vm_fqdn)"
[[ -n "$FQDN" ]] || sakai_die 'VM has no public FQDN.'

exec scp \
  -o BatchMode=yes \
  -o ConnectTimeout=15 \
  -o ConnectionAttempts=2 \
  -o StrictHostKeyChecking=accept-new \
  -i "$SAKAI_SSH_KEY" \
  "$1" "$SAKAI_VM_USER@$FQDN:$2"
