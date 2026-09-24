#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/deployment/.env"
SUBSCRIPTION_ID='55a5701c-411e-45f1-9829-9c80f526d9eb'
RESOURCE_GROUP='rg-sakai-mcp-dev'
LOCATION='koreacentral'

if [[ ! -f "$ENV_FILE" ]]; then
  umask 077
  MYSQL_ADMIN_PASSWORD="$(openssl rand -base64 36 | tr -d '\n' | tr -dc 'A-Za-z0-9@#%+=_' | cut -c1-32)"
  [[ ${#MYSQL_ADMIN_PASSWORD} -ge 16 ]] || { echo 'Unable to generate a database password.' >&2; exit 1; }
  printf 'MYSQL_ADMIN_PASSWORD=%q\n' "$MYSQL_ADMIN_PASSWORD" > "$ENV_FILE"
  echo "Generated a database password in $ENV_FILE (mode 600; ignored by Git)."
fi

# shellcheck disable=SC1090
source "$ENV_FILE"
[[ -n "${MYSQL_ADMIN_PASSWORD:-}" ]] || { echo 'MYSQL_ADMIN_PASSWORD is missing from deployment/.env' >&2; exit 1; }

CURRENT_SUBSCRIPTION="$(az account show --query id -o tsv)"
if [[ "$CURRENT_SUBSCRIPTION" != "$SUBSCRIPTION_ID" ]]; then
  echo "Refusing: selected subscription is $CURRENT_SUBSCRIPTION; expected $SUBSCRIPTION_ID." >&2
  exit 1
fi

SSH_KEY_PATH="${SAKAI_SSH_PUBLIC_KEY:-$HOME/.ssh/buriPersonal.pub}"
[[ -r "$SSH_KEY_PATH" ]] || { echo "SSH public key not readable: $SSH_KEY_PATH" >&2; exit 1; }
ADMIN_CIDR="${SAKAI_ADMIN_CIDR:-$(curl -fsS --max-time 20 https://api.ipify.org)/32}"

if [[ "$(az group exists --name "$RESOURCE_GROUP")" == 'true' ]]; then
  EXISTING_RG_LOCATION="$(az group show --name "$RESOURCE_GROUP" --query location -o tsv)"
  echo "Using existing resource group $RESOURCE_GROUP (metadata location: $EXISTING_RG_LOCATION)."
else
  az group create --name "$RESOURCE_GROUP" --location "$LOCATION" \
    --tags project=sakai-mcp environment=dev purpose=lms-sandbox owner=burhan managed-by=bicep \
    --output none
fi

az group update --name "$RESOURCE_GROUP" \
  --tags project=sakai-mcp environment=dev purpose=lms-sandbox owner=burhan managed-by=bicep \
  --output none

az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --name sakai-dev-infra \
  --template-file "$ROOT_DIR/deployment/infra/main.bicep" \
  --parameters "$ROOT_DIR/deployment/infra/parameters/dev.bicepparam" \
  --parameters adminSshPublicKey="$(<"$SSH_KEY_PATH")" adminSourceCidr="$ADMIN_CIDR" mysqlAdminPassword="$MYSQL_ADMIN_PASSWORD" \
  --output json
