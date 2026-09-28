#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -lt 2 || $# -gt 3 || ( $# -eq 3 && "$3" != '--push-only' ) ]]; then
  echo 'Usage: deployment/release-mcp.sh SOURCE_COMMIT SCANNED_LOCAL_IMAGE [--push-only]' >&2
  exit 2
fi

source_commit="$1"
local_image="$2"
push_only="${3:-}"
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]] || { echo 'SOURCE_COMMIT must be a full lowercase Git SHA.' >&2; exit 2; }
[[ -n "$local_image" ]] || { echo 'A locally built and scanned image tag is required.' >&2; exit 2; }
command -v az >/dev/null || { echo 'Azure CLI is required.' >&2; exit 2; }
command -v docker >/dev/null || { echo 'Docker is required.' >&2; exit 2; }
command -v curl >/dev/null || { echo 'curl is required.' >&2; exit 2; }
command -v python3 >/dev/null || { echo 'Python 3 is required.' >&2; exit 2; }

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
resource_group='rg-sakai-mcp-dev'
app_name='ca-mcp-sakai-dev'
canonical_origin='https://mcp.smartdigest.app'
expected_subscription='55a5701c-411e-45f1-9829-9c80f526d9eb'
selected_subscription="$(az account show --query id -o tsv)"
[[ "$selected_subscription" == "$expected_subscription" ]] || {
  echo "Refusing: selected subscription is $selected_subscription; expected $expected_subscription." >&2
  exit 2
}

docker image inspect "$local_image" >/dev/null
image_commit="$(docker image inspect "$local_image" --format '{{index .Config.Labels "org.opencontainers.image.revision"}}')"
lock_sha="$(docker image inspect "$local_image" --format '{{index .Config.Labels "org.opencontainers.image.uv-lock-sha256"}}')"
[[ "$image_commit" == "$source_commit" && "$lock_sha" =~ ^[0-9a-f]{64}$ ]] || {
  echo 'The scanned local image does not have the requested commit and lock identity.' >&2
  exit 2
}

registry_count="$(az acr list --resource-group "$resource_group" --query 'length(@)' -o tsv)"
[[ "$registry_count" == 1 ]] || { echo 'Expected exactly one MCP ACR in the resource group.' >&2; exit 2; }
registry_name="$(az acr list --resource-group "$resource_group" --query '[0].name' -o tsv)"
registry_server="$(az acr show --resource-group "$resource_group" --name "$registry_name" --query loginServer -o tsv)"
if [[ "$push_only" != '--push-only' ]]; then
  app_json="$(az containerapp show --resource-group "$resource_group" --name "$app_name" -o json 2>/dev/null)" || {
    echo 'MCP Container App is absent. Complete the Phase 18 Bicep bootstrap before this revision release.' >&2
    exit 2
  }
  previous_image="$(python3 -c 'import json,sys; a=json.load(sys.stdin); print(a["properties"]["template"]["containers"][0]["image"])' <<< "$app_json")"
  app_fqdn="$(python3 -c 'import json,sys; a=json.load(sys.stdin); print(a["properties"]["configuration"]["ingress"]["fqdn"])' <<< "$app_json")"
  entra_tenant_id="$(python3 -c 'import json,sys; e={x["name"]:x.get("value","") for x in json.load(sys.stdin)["properties"]["template"]["containers"][0]["env"]}; print(e.get("ENTRA_TENANT_ID", ""))' <<< "$app_json")"
  mcp_client_id="$(python3 -c 'import json,sys; e={x["name"]:x.get("value","") for x in json.load(sys.stdin)["properties"]["template"]["containers"][0]["env"]}; print(e.get("MCP_RESOURCE_CLIENT_ID", ""))' <<< "$app_json")"
  [[ -n "$registry_server" && -n "$app_fqdn" && "$app_fqdn" != None && -n "$entra_tenant_id" && -n "$mcp_client_id" ]] || {
    echo 'MCP registry or HTTPS ingress is incomplete.' >&2
    exit 2
  }
  mcp_hostname="${canonical_origin#https://}"
  python3 -c '
import json
import sys
app = json.loads(sys.stdin.read())
hostname = sys.argv[1]
domains = app["properties"]["configuration"]["ingress"].get("customDomains", [])
assert any(d.get("name") == hostname and d.get("bindingType") == "SniEnabled" for d in domains), "Canonical hostname is not SNI-bound on the Container App."
' <<< "$app_json" "$mcp_hostname"
fi

tag="${registry_server}/sakai-mcp:${source_commit}"
echo "Publishing scanned commit $source_commit to $registry_name."
az acr login --name "$registry_name" --output none
docker tag "$local_image" "$tag"
docker push "$tag" >/dev/null
digest="$(az acr manifest show-metadata --registry "$registry_name" --name "sakai-mcp:$source_commit" --query digest -o tsv)"
[[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || { echo 'ACR did not return an immutable SHA-256 digest.' >&2; exit 1; }
image="${registry_server}/sakai-mcp@${digest}"

if [[ "$push_only" == '--push-only' ]]; then
  echo "Scanned image ready for Phase 18 app bootstrap: $image"
  echo "Commit: $source_commit"
  echo "Lock SHA-256: $lock_sha"
  exit 0
fi

echo "Previous image: $previous_image"
echo "Deploying digest: $image"
az containerapp update --resource-group "$resource_group" --name "$app_name" \
  --image "$image" --set-env-vars "APP_COMMIT=$source_commit" "APP_LOCK_SHA256=$lock_sha" \
  "MCP_PUBLIC_URL=$canonical_origin" "MCP_AUDIENCE=$mcp_client_id" \
  "MCP_ISSUER=https://login.microsoftonline.com/$entra_tenant_id/v2.0" \
  "MCP_JWKS_URI=https://login.microsoftonline.com/$entra_tenant_id/discovery/v2.0/keys" \
  "SAKAI_ISSUER=https://sts.windows.net/$entra_tenant_id/" \
  --output none

ready_revision=''
for attempt in {1..30}; do
  latest_revision="$(az containerapp show --resource-group "$resource_group" --name "$app_name" \
    --query properties.latestRevisionName -o tsv)"
  ready_revision="$(az containerapp show --resource-group "$resource_group" --name "$app_name" \
    --query properties.latestReadyRevisionName -o tsv)"
  if [[ -n "$latest_revision" && "$latest_revision" == "$ready_revision" ]]; then
    break
  fi
  sleep 10
done
[[ -n "$ready_revision" && "$latest_revision" == "$ready_revision" ]] || {
  echo 'Latest MCP revision did not become ready within five minutes.' >&2
  exit 1
}

origin="$canonical_origin"
curl --fail --silent --show-error --max-time 15 --retry 24 --retry-delay 10 --retry-all-errors \
  "$origin/live" >/dev/null
curl --fail --silent --show-error --max-time 15 --retry 12 --retry-delay 5 --retry-all-errors \
  "$origin/ready" >/dev/null

headers="$(mktemp)"
trap 'rm -f "$headers"' EXIT
status="$(curl --silent --show-error --max-time 20 --dump-header "$headers" --output /dev/null \
  --write-out '%{http_code}' --request POST --header 'Content-Type: application/json' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' "$origin/mcp")"
[[ "$status" == 401 ]] || { echo "Unauthenticated MCP request returned HTTP $status; expected 401." >&2; exit 1; }
grep -Eiq '^www-authenticate: *Bearer' "$headers" || {
  echo 'Unauthenticated MCP response lacks the Bearer challenge.' >&2
  exit 1
}
curl --fail --silent --show-error --max-time 20 \
  "$origin/.well-known/oauth-protected-resource" | \
  python3 -c 'import json,sys; data=json.load(sys.stdin); assert data.get("resource") == sys.argv[1]; assert data.get("authorization_servers")' "$origin"

az containerapp show --resource-group "$resource_group" --name "$app_name" -o json | \
  python3 -c '
import json
import sys
app = json.load(sys.stdin)
expected_image, expected_commit = sys.argv[1:]
assert app["properties"]["template"]["containers"][0]["image"] == expected_image
env = {entry["name"]: entry.get("value") for entry in app["properties"]["template"]["containers"][0]["env"]}
assert env.get("APP_COMMIT") == expected_commit
assert env.get("MCP_PUBLIC_URL") == "https://mcp.smartdigest.app"
assert env.get("MCP_AUDIENCE") == env.get("MCP_RESOURCE_CLIENT_ID")
tenant = env["ENTRA_TENANT_ID"]
assert env.get("MCP_ISSUER") == f"https://login.microsoftonline.com/{tenant}/v2.0"
assert env.get("SAKAI_ISSUER") == f"https://sts.windows.net/{tenant}/"
assert app["properties"]["configuration"]["ingress"].get("stickySessions", {}).get("affinity", "none").lower() == "none"
assert app["properties"]["latestRevisionName"] == app["properties"]["latestReadyRevisionName"]
' "$image" "$source_commit"

echo "MCP digest release passed HTTP probes, OAuth challenge, metadata, image, and affinity checks."
echo "Commit: $source_commit"
echo "Digest: $image"
echo "Revision: $(az containerapp show --resource-group "$resource_group" --name "$app_name" --query properties.latestReadyRevisionName -o tsv)"
echo "Rollback image: $previous_image"
