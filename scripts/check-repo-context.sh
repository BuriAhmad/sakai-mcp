#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
missing=0

for area in services deployment; do
  if [[ "$area" == services ]]; then
    guide="$ROOT_DIR/AGENTS.md"
  else
    guide="$ROOT_DIR/deployment/AGENTS.md"
  fi

  for directory in "$ROOT_DIR/$area"/*/; do
    [[ -d "$directory" ]] || continue
    relative="${directory#"$ROOT_DIR/"}"
    # Runtime-only directories such as deployment/artifacts/ do not form part
    # of the repository layout and must not need tracked guidance files.
    if git -C "$ROOT_DIR" check-ignore -q -- "$relative"; then
      continue
    fi

    if [[ ! -f "${directory}README.md" ]]; then
      printf 'Missing README: %sREADME.md\n' "$relative" >&2
      missing=1
    fi

    if ! grep -Fq -- "$relative" "$guide"; then
      printf 'Missing guide entry: %s in %s\n' "$relative" "${guide#"$ROOT_DIR/"}" >&2
      missing=1
    fi
  done
done

if ((missing)); then
  exit 1
fi

printf 'Repository guidance covers service and deployment directories.\n'
