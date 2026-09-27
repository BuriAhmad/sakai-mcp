#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 3 ]]; then
  echo 'Usage: scripts/build-mcp-image.sh CONTEXT_DIR LOCAL_IMAGE_TAG SOURCE_COMMIT' >&2
  exit 2
fi

context_dir="$(cd "$1" && pwd)"
image_tag="$2"
source_commit="$3"
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || { echo 'SOURCE_COMMIT must be a full lowercase Git SHA.' >&2; exit 2; }
[[ -r "$context_dir/uv.lock" && -r "$context_dir/Dockerfile" ]] || { echo 'MCP build context is incomplete.' >&2; exit 2; }
command -v docker >/dev/null || { echo 'Docker is required.' >&2; exit 2; }
command -v python3 >/dev/null || { echo 'Python 3 is required to summarize scan results.' >&2; exit 2; }

lock_sha="$(shasum -a 256 "$context_dir/uv.lock" | awk '{print $1}')"
scan_dir="$(mktemp -d)"
trap 'rm -rf "$scan_dir"' EXIT
mkdir "$scan_dir/cache"
scanner='ghcr.io/aquasecurity/trivy:0.74.0@sha256:62b1e65e8869bc4b4c6aa4fa2b21595256c7c2f6018a9d9ad61caf87187c1969'

summarize_scan() {
  python3 - "$1" <<'PY'
import json
import pathlib
import sys

report = pathlib.Path(sys.argv[1])
if not report.is_file():
    print('Scanner returned no report; inspect scanner diagnostics.', file=sys.stderr)
    sys.exit(1)
results = json.loads(report.read_text()).get('Results', [])
vulnerabilities = [finding for item in results for finding in item.get('Vulnerabilities') or []]
critical = sum(finding.get('Severity') == 'CRITICAL' for finding in vulnerabilities)
fixable_high = sum(
    finding.get('Severity') == 'HIGH' and bool(finding.get('FixedVersion'))
    for finding in vulnerabilities
)
unfixed_high = sum(
    finding.get('Severity') == 'HIGH' and not finding.get('FixedVersion')
    for finding in vulnerabilities
)
secrets = sum(len(item.get('Secrets') or []) for item in results)
print(f'Scan summary: {critical} critical; {fixable_high} fixable high; '
      f'{unfixed_high} high without a published fix; {secrets} secrets.')
if critical or fixable_high or secrets:
    sys.exit(1)
PY
}

echo 'Scanning MCP source and locked dependencies.'
docker run --rm \
  --user "$(id -u):$(id -g)" --env TRIVY_CACHE_DIR=/reports/cache \
  --mount "type=bind,source=$context_dir,target=/src,readonly" \
  --mount "type=bind,source=$scan_dir,target=/reports" \
  "$scanner" fs --quiet --scanners vuln,secret --severity HIGH,CRITICAL \
  --skip-dirs /src/.venv --skip-dirs /src/.pytest_cache --skip-dirs /src/.mypy_cache \
  --format json --output /reports/source.json /src
summarize_scan "$scan_dir/source.json"

echo 'Building locked, non-root MCP image.'
docker build --platform linux/amd64 \
  --build-arg "SOURCE_COMMIT=$source_commit" \
  --build-arg "LOCK_SHA256=$lock_sha" \
  --tag "$image_tag" "$context_dir"
docker save --output "$scan_dir/image.tar" "$image_tag"

echo 'Scanning the built image.'
docker run --rm \
  --user "$(id -u):$(id -g)" --env TRIVY_CACHE_DIR=/reports/cache \
  --mount "type=bind,source=$scan_dir,target=/reports" \
  "$scanner" image --quiet --scanners vuln,secret --severity HIGH,CRITICAL \
  --input /reports/image.tar --format json --output /reports/image.json
summarize_scan "$scan_dir/image.json"

echo "MCP image ready locally: $image_tag (commit $source_commit; lock $lock_sha)."
