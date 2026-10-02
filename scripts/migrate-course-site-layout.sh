#!/usr/bin/env bash
set -Eeuo pipefail

[[ $# -eq 0 ]] || { echo 'Usage: ./sakai migrate-course-layout' >&2; exit 2; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITES_FILE="$ROOT_DIR/deployment/mcp-test-sites.env"
REMOTE_SCRIPT="$ROOT_DIR/deployment/run-course-site-layout-migration.sh"

[[ -r "$SITES_FILE" ]] || { echo "Missing $SITES_FILE; refusing to guess site IDs." >&2; exit 1; }
# This file is ignored and contains the exact synthetic MCP Course A/B IDs.
# shellcheck disable=SC1090
source "$SITES_FILE"
for site_id in "${SITE_A:-}" "${SITE_B:-}"; do
  [[ "$site_id" =~ ^[A-Za-z0-9_-]+$ ]] || { echo 'Course A/B site IDs are missing or invalid.' >&2; exit 1; }
done

printf 'Applying course layout v2 and Student roster visibility to Course A/B and the course authorization template.\n'
"$ROOT_DIR/sakai" shell "sudo bash -s -- '$SITE_A' '$SITE_B'" < "$REMOTE_SCRIPT"
