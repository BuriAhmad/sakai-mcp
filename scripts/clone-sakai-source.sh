#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/source/sakai"
SAKAI_REPOSITORY="${SAKAI_GIT_URL:-https://github.com/sakaiproject/sakai.git}"
SAKAI_TAG="${SAKAI_TAG:-25.2}"
SAKAI_WORK_BRANCH="${SAKAI_WORK_BRANCH:-sakai-mcp/25.2}"
EXPECTED_COMMIT='b5b7800f0fcddf9d0db47276a66065189365d905'

command -v git >/dev/null 2>&1 || { echo "Error: Git is required." >&2; exit 1; }

if [[ -d "$SOURCE_DIR/.git" ]]; then
  echo "Sakai source already exists at $SOURCE_DIR"
  git -C "$SOURCE_DIR" status --short --branch
  exit 0
fi

[[ ! -e "$SOURCE_DIR" ]] || {
  echo "Error: $SOURCE_DIR exists but is not a Git checkout." >&2
  exit 1
}

echo "Cloning Sakai $SAKAI_TAG into $SOURCE_DIR..."
git clone --branch "$SAKAI_TAG" --single-branch "$SAKAI_REPOSITORY" "$SOURCE_DIR"

actual_commit="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
if [[ "$SAKAI_REPOSITORY" == 'https://github.com/sakaiproject/sakai.git' && "$actual_commit" != "$EXPECTED_COMMIT" ]]; then
  echo "Warning: tag $SAKAI_TAG now resolves to $actual_commit, not the deployed $EXPECTED_COMMIT." >&2
fi

if [[ -z "$(git -C "$SOURCE_DIR" symbolic-ref --short --quiet HEAD)" ]]; then
  git -C "$SOURCE_DIR" switch --create "$SAKAI_WORK_BRANCH"
fi

echo "Sakai source is ready at $SOURCE_DIR"
echo 'This checkout has its own Git history; do not commit it into the infrastructure repository.'
