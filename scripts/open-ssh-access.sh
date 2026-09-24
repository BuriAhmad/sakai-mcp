#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib/azure.sh
source "$SCRIPT_DIR/lib/azure.sh"

sakai_open_ssh_for_this_mac
