#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/ssh.sh
source "$ROOT_DIR/scripts/lib/ssh.sh"

[[ $# -eq 1 && "$1" =~ ^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$ ]] || {
  echo 'Usage: ./sakai rollback RELEASE_ID' >&2
  exit 2
}
release_id="$1"
sakai_require_command ssh
sakai_require_command scp
sakai_require_private_key
sakai_require_azure_login
sakai_require_vm_running
sakai_open_ssh_for_this_mac
fqdn="$(sakai_vm_fqdn)"
[[ "$fqdn" =~ ^[A-Za-z0-9.-]+$ && -n "$fqdn" ]] || sakai_die 'VM has no valid public FQDN.'

ssh_options=(-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30
  -o ServerAliveCountMax=10 -o StrictHostKeyChecking=accept-new -i "$SAKAI_SSH_KEY")
remote="$SAKAI_VM_USER@$fqdn"
remote_dir="$(ssh "${ssh_options[@]}" "$remote" 'mktemp -d /var/tmp/sakai-rollback.XXXXXXXX')"
[[ "$remote_dir" =~ ^/var/tmp/sakai-rollback\.[A-Za-z0-9]{8}$ ]] || \
  sakai_die 'Unexpected remote temporary directory.'
scp "${ssh_options[@]}" "$ROOT_DIR/deployment/release-sakai-vm.sh" "$remote:$remote_dir/"
ssh "${ssh_options[@]}" "$remote" \
  "sudo -n bash '$remote_dir/release-sakai-vm.sh' rollback '$release_id'"
echo "Rollback complete. Verify https://$fqdn/portal and any affected Sakai features."
