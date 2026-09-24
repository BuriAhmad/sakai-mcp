#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/azure.sh
source "$ROOT_DIR/scripts/lib/azure.sh"

usage() {
  echo "Usage: ./sakai deploy COMMIT [--check-only]" >&2
  exit 2
}

[[ $# -ge 1 && $# -le 2 ]] || usage
requested_commit="$1"
[[ "$requested_commit" == HEAD || "$requested_commit" =~ ^[0-9a-fA-F]{7,40}$ ]] || usage
[[ $# -eq 1 || "$2" == --check-only ]] || usage

sakai_require_command git
sakai_require_command gzip
sakai_require_command shasum
sakai_require_command mktemp

commit="$(git -C "$ROOT_DIR" rev-parse --verify --end-of-options "${requested_commit}^{commit}")" || \
  sakai_die "Unknown commit: $requested_commit"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || sakai_die 'Expected a complete Git commit SHA.'

git -C "$ROOT_DIR" fetch --quiet origin main
git -C "$ROOT_DIR" merge-base --is-ancestor "$commit" refs/remotes/origin/main || \
  sakai_die 'The selected commit is not on the pushed origin/main branch.'
git -C "$ROOT_DIR" cat-file -e "$commit:apps/sakai/pom.xml" || \
  sakai_die 'The selected commit has no Sakai source at apps/sakai/.'

if [[ -n "$(git -C "$ROOT_DIR" status --porcelain -- apps/sakai)" ]]; then
  sakai_die 'Sakai has uncommitted changes. Commit and push them, or set them aside before deploying.'
fi
for path in sakai scripts/deploy-sakai-release.sh deployment/release-sakai-vm.sh; do
  if [[ -n "$(git -C "$ROOT_DIR" status --porcelain -- "$path")" ]]; then
    sakai_die "Deployment code has uncommitted changes: $path"
  fi
done

echo "Selected pushed commit: $commit"
echo 'Target: rg-sakai-mcp-dev / vm-sakai-dev (development environment)'
if [[ "${2:-}" == --check-only ]]; then
  echo 'Check only: no Azure resource or VM was changed.'
  exit 0
fi

sakai_require_command ssh
sakai_require_command scp
sakai_require_command curl
sakai_require_private_key
sakai_require_azure_login

db_state="$(az mysql flexible-server show \
  --resource-group "$SAKAI_RESOURCE_GROUP" \
  --name mysql-sakai-dev-55a5701c-uae --query state --output tsv)"
[[ "$db_state" == Ready ]] || sakai_die "MySQL must be Ready before deployment (currently: $db_state)."

temp_dir="$(mktemp -d "${TMPDIR:-/tmp}/sakai-release.XXXXXXXX")"
[[ "$temp_dir" =~ ^/.*/sakai-release\.[A-Za-z0-9]{8}$ ]] || \
  sakai_die 'Unexpected local temporary directory.'
cleanup() { rm -r -- "$temp_dir"; }
trap cleanup EXIT
git -C "$ROOT_DIR" archive --format=tar "$commit" apps/sakai | gzip -1 > "$temp_dir/source.tar.gz"
archive_sha256="$(shasum -a 256 "$temp_dir/source.tar.gz" | awk '{print $1}')"
release_id="$(date -u +%Y%m%dT%H%M%SZ)-${commit:0:12}"

echo 'This build stops Tomcat for its duration and may take a long time.'
echo "Release ID: $release_id"
sakai_open_ssh_for_this_mac
sakai_ensure_vm_running
fqdn="$(sakai_vm_fqdn)"
[[ "$fqdn" =~ ^[A-Za-z0-9.-]+$ && -n "$fqdn" ]] || sakai_die 'VM has no valid public FQDN.'

ssh_options=(-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30
  -o ServerAliveCountMax=10 -o StrictHostKeyChecking=accept-new -i "$SAKAI_SSH_KEY")
remote="$SAKAI_VM_USER@$fqdn"
remote_dir="$(ssh "${ssh_options[@]}" "$remote" 'mktemp -d /var/tmp/sakai-release.XXXXXXXX')"
[[ "$remote_dir" =~ ^/var/tmp/sakai-release\.[A-Za-z0-9]{8}$ ]] || \
  sakai_die 'Unexpected remote temporary directory.'

scp "${ssh_options[@]}" "$temp_dir/source.tar.gz" \
  "$ROOT_DIR/deployment/release-sakai-vm.sh" "$remote:$remote_dir/"
echo 'Building and deploying on the VM. Build log is kept under /opt/sakai-releases/.'
ssh "${ssh_options[@]}" "$remote" \
  "sudo -n bash '$remote_dir/release-sakai-vm.sh' deploy '$commit' '$archive_sha256' '$remote_dir/source.tar.gz' '$release_id'"

echo 'Checking the public HTTPS portal from this Mac...'
public_ok=0
for _ in {1..12}; do
  if curl --fail --silent --show-error --max-time 20 --output /dev/null \
    "https://$fqdn/portal"; then
    public_ok=1
    break
  fi
  sleep 10
done
if [[ "$public_ok" -ne 1 ]]; then
  echo 'Public HTTPS check failed; requesting rollback.' >&2
  ssh "${ssh_options[@]}" "$remote" \
    "sudo -n bash '$remote_dir/release-sakai-vm.sh' rollback '$release_id'" || true
  sakai_die "Deployment was rolled back or needs manual recovery. Inspect /opt/sakai-releases/$release_id."
fi

echo "Deployment healthy: $commit"
echo "Portal: https://$fqdn/portal"
echo "Rollback, if needed: ./sakai rollback $release_id"
