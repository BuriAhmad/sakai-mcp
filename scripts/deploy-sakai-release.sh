#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/lib/azure.sh
source "$ROOT_DIR/scripts/lib/azure.sh"

usage() {
  echo "Usage: ./sakai deploy COMMIT [--check-only]" >&2
  exit 2
}

[[ $# -ge 1 ]] || usage
requested_commit="$1"
shift
[[ "$requested_commit" == HEAD || "$requested_commit" =~ ^[0-9a-fA-F]{7,40}$ ]] || usage
check_only=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-only)
      [[ "$check_only" -eq 0 ]] || usage
      check_only=1
      shift
      ;;
    *) usage ;;
  esac
done

sakai_require_command git
sakai_require_command gzip
sakai_require_command shasum
sakai_require_command mktemp

commit="$(git -C "$ROOT_DIR" rev-parse --verify --end-of-options "${requested_commit}^{commit}")" || \
  sakai_die "Unknown commit: $requested_commit"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || sakai_die 'Expected a complete Git commit SHA.'

# Releases must come from main. Feature branches are merged and pushed before release.
# Fetch main explicitly so an old local reference cannot admit an unpushed release.
git -C "$ROOT_DIR" fetch --quiet origin \
  'refs/heads/main:refs/remotes/origin/main'
git -C "$ROOT_DIR" merge-base --is-ancestor "$commit" refs/remotes/origin/main || \
  sakai_die 'The selected commit is not on pushed origin/main. Merge and push before deploying.'
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
echo 'Release source: origin/main'
echo 'Target: rg-sakai-mcp-dev / vm-sakai-dev (development environment)'
if [[ "$check_only" -eq 1 ]]; then
  echo 'Check only: no Azure resource or VM was changed.'
  exit 0
fi

sakai_require_command ssh
sakai_require_command scp
sakai_require_command curl
sakai_require_private_key
sakai_require_azure_login
sakai_require_vm_running

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
# A transient VM-owned unit keeps the guarded release alive if this SSH client drops.
unit_name="sakai-release-$release_id.service"
ssh "${ssh_options[@]}" "$remote" \
  "sudo -n systemd-run --no-block --unit='$unit_name' --property=Type=oneshot --property=RemainAfterExit=yes /bin/bash '$remote_dir/release-sakai-vm.sh' deploy '$commit' '$archive_sha256' '$remote_dir/source.tar.gz' '$release_id'"
echo "VM release unit: $unit_name"
echo "Monitor: ./sakai shell 'sudo journalctl -u $unit_name --no-pager -n 30'"

release_ok=0
previous_state=''
for _ in {1..240}; do
  if remote_state="$(ssh "${ssh_options[@]}" "$remote" \
    "systemctl show '$unit_name' --property=ActiveState --property=Result" \
    2>"$temp_dir/monitor-error")"; then
    if [[ "$remote_state" != "$previous_state" ]]; then
      echo "$remote_state"
      previous_state="$remote_state"
    fi
    case "$remote_state" in
      *ActiveState=active*)
        if [[ "$remote_state" == *Result=success* ]]; then
          release_ok=1
          break
        fi
        ;;
      *ActiveState=failed*|*ActiveState=inactive*)
        ssh "${ssh_options[@]}" "$remote" \
          "sudo -n journalctl -u '$unit_name' --no-pager -n 50" || true
        sakai_die "VM release failed. Inspect $unit_name and /opt/sakai-releases/$release_id."
        ;;
    esac
  else
    if [[ "$previous_state" != disconnected ]]; then
      echo 'Release monitor disconnected; the guarded VM job continues. Reconnecting...'
      previous_state=disconnected
    fi
  fi
  sleep 15
done
[[ "$release_ok" -eq 1 ]] || \
  sakai_die "Timed out monitoring $unit_name; the VM job may still be running. Inspect it before starting another release."
remote_status="$(ssh "${ssh_options[@]}" "$remote" \
  "sudo -n cat '/opt/sakai-releases/$release_id/status'")"
[[ "$remote_status" == healthy ]] || sakai_die "VM release did not record healthy: $remote_status"

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
