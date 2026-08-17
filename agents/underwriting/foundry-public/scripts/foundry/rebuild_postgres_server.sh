#!/usr/bin/env bash
set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

require_bin az
require_bin azd
require_bin make

get_env_value() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
}

required_env_value() {
  local key="$1"
  local value
  value="$(get_env_value "$key")"
  if [[ -z "$value" ]]; then
    echo "Missing selected AZD environment value: $key" >&2
    exit 1
  fi
  printf '%s' "$value"
}

SUBSCRIPTION_ID="$(required_env_value AZURE_SUBSCRIPTION_ID)"
RESOURCE_GROUP="$(required_env_value AZURE_RESOURCE_GROUP)"
SERVER_NAME="$(required_env_value POSTGRES_SERVER_NAME)"
SERVER_LOCATION="$(required_env_value POSTGRES_SERVER_LOCATION)"
DATABASE_NAME="$(required_env_value POSTGRES_DATABASE)"
INFRASTRUCTURE_MODE="$(required_env_value INFRASTRUCTURE_MODE)"
if [[ "$INFRASTRUCTURE_MODE" != "bootstrap" ]]; then
  echo "PostgreSQL rebuild requires a bootstrap-mode environment that guarantees declarative recreation; refusing to delete from '$INFRASTRUCTURE_MODE' mode." >&2
  exit 1
fi

# A recreated server needs a new administrator password, not the unavailable
# password of the deleted server. Persist it only in the local azd environment.
admin_password="$(
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value POSTGRES_ADMIN_PASSWORD --cwd "$FOUNDRY_DIR" --no-prompt
)"
if [[ -z "$admin_password" ]]; then
  require_bin openssl
  admin_password="Pgsql!9$(openssl rand -hex 32)"
  if ! AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env set POSTGRES_ADMIN_PASSWORD "$admin_password" --cwd "$FOUNDRY_DIR" --no-prompt >/dev/null; then
    echo "Unable to save the new PostgreSQL administrator password in the local azd environment." >&2
    exit 1
  fi
  echo "Generated a new PostgreSQL administrator password in the local azd environment."
fi
unset admin_password

az account set --subscription "$SUBSCRIPTION_ID"
active_subscription="$(az account show --query id --output tsv)"
if [[ "$active_subscription" != "$SUBSCRIPTION_ID" ]]; then
  echo "Azure CLI did not select the expected subscription; refusing to delete." >&2
  exit 1
fi

if ! az postgres flexible-server list-skus --location "$SERVER_LOCATION" --output json \
  | grep -Fq '"name": "Standard_D2ds_v5"'; then
  echo "The selected Standard_D2ds_v5 SKU is unavailable in $SERVER_LOCATION; refusing to delete." >&2
  exit 1
fi

# Listing is intentionally scoped to the selected AZD environment. This makes
# a retry after a failed provision safe: an already-deleted server is
# recreated, never substituted with a server selected by caller input.
existing_server="$(
  az postgres flexible-server list \
    --subscription "$SUBSCRIPTION_ID" \
    --resource-group "$RESOURCE_GROUP" \
    --query "[?name=='$SERVER_NAME'].name | [0]" \
    --output tsv
)"

if [[ "$existing_server" == "$SERVER_NAME" ]]; then
  actual_server_location="$(
    az postgres flexible-server show \
      --subscription "$SUBSCRIPTION_ID" \
      --resource-group "$RESOURCE_GROUP" \
      --name "$SERVER_NAME" \
      --query location \
      --output tsv
  )"
  configured_location="$(tr '[:upper:]' '[:lower:]' <<<"$SERVER_LOCATION" | tr -d '[:space:]')"
  actual_location="$(tr '[:upper:]' '[:lower:]' <<<"$actual_server_location" | tr -d '[:space:]')"
  if [[ "$actual_location" != "$configured_location" ]]; then
    echo "Selected AZD PostgreSQL location '$SERVER_LOCATION' does not match the existing server location '$actual_server_location'; refusing to delete." >&2
    exit 1
  fi

  echo "Deleting PostgreSQL Flexible Server '$SERVER_NAME' in '$RESOURCE_GROUP'."
  az postgres flexible-server delete \
    --subscription "$SUBSCRIPTION_ID" \
    --resource-group "$RESOURCE_GROUP" \
    --name "$SERVER_NAME" \
    --yes
  echo "Waiting for PostgreSQL Flexible Server deletion to finish."
  az postgres flexible-server wait \
    --subscription "$SUBSCRIPTION_ID" \
    --resource-group "$RESOURCE_GROUP" \
    --name "$SERVER_NAME" \
    --deleted \
    --interval 15 \
    --timeout 1800
else
  echo "PostgreSQL Flexible Server '$SERVER_NAME' is already absent; continuing with declarative recreation."
fi

echo "Recreating '$SERVER_NAME' and database resources through Bicep."
# The selected AZD environment remains the single source of truth. This flag
# lets the hydration script preserve its PostgreSQL location while the server
# is absent between deletion and Bicep recreation.
POSTGRES_REBUILD=1 make -C "$ROOT_DIR" foundry-provision
