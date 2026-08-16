#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
TEMPLATE_FILE="$FOUNDRY_DIR/iac/modules/foundry-project-runtime-secret-connection.bicep"
RESULTS_DIR="$ROOT_DIR/backend/.foundry/results"
METADATA_FILE="${FOUNDRY_RUNTIME_CONNECTION_METADATA_FILE:-$RESULTS_DIR/runtime-connection-deployment.json}"
SCRATCH_DIR="$ROOT_DIR/backend/.tmp/runtime-connection"
PARAMETER_FILE="$SCRATCH_DIR/order-resolution-runtime-connection-${BASHPID}.json"
DEPLOYMENT_NAME="order-resolution-runtime-secret-connection"

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
}

required_env() {
  local name="$1"
  local value
  value="$(get_env "$name")"
  [[ -n "$value" ]] || {
    echo "Missing AZD environment value: $name" >&2
    exit 1
  }
  printf '%s' "$value"
}

cleanup() {
  rm -f -- "$PARAMETER_FILE"
}

trap cleanup EXIT HUP INT TERM
umask 077
mkdir -p "$SCRATCH_DIR"

for command in az azd jq python3; do
  require_bin "$command"
done
[[ -f "$TEMPLATE_FILE" ]] || {
  echo "Runtime connection Bicep template is missing: $TEMPLATE_FILE" >&2
  exit 1
}

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
location="$(required_env AZURE_LOCATION)"
account_name="$(required_env FOUNDRY_ACCOUNT_NAME)"
project_name="$(required_env FOUNDRY_PROJECT_NAME)"
runtime_database_url="$(required_env RUNTIME_DATABASE_URL)"
postgres_server_name="$(required_env POSTGRES_SERVER_NAME)"
connection_name="${FOUNDRY_RUNTIME_CONNECTION_NAME:-$(get_env FOUNDRY_RUNTIME_CONNECTION_NAME)}"
connection_name="${connection_name:-orderresolutionruntimesecrets}"

[[ "$subscription_id" == "7df95e88-701c-4693-af77-3159f83b558d" ]] || {
  echo "Runtime connection convergence requires the canonical public subscription." >&2
  exit 1
}
[[ "$resource_group" == "rg-langgraph-ora-foundry-public" ]] || {
  echo "Runtime connection convergence requires the canonical public resource group." >&2
  exit 1
}
[[ "${location,,}" == "eastus2" ]] || {
  echo "Runtime connection convergence requires the canonical eastus2 location." >&2
  exit 1
}
[[ "$connection_name" == "orderresolutionruntimesecrets" ]] || {
  echo "Unexpected runtime connection name: $connection_name" >&2
  exit 1
}
[[ "$runtime_database_url" == postgresql+psycopg://* ]] &&
  [[ "$runtime_database_url" == *"${postgres_server_name}.postgres.database.azure.com"* ]] &&
  [[ "$runtime_database_url" == *"sslmode=require"* ]] || {
  echo "RUNTIME_DATABASE_URL must be the canonical TLS PostgreSQL runtime URL." >&2
  exit 1
}

export RUNTIME_CONNECTION_PARAMETER_FILE="$PARAMETER_FILE"
export RUNTIME_CONNECTION_ACCOUNT_NAME="$account_name"
export RUNTIME_CONNECTION_PROJECT_NAME="$project_name"
export RUNTIME_CONNECTION_LOCATION="$location"
export RUNTIME_CONNECTION_NAME="$connection_name"
export RUNTIME_CONNECTION_DATABASE_URL="$runtime_database_url"
python3 - <<'PY'
import json
import os
from pathlib import Path

payload = {
    "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
    "contentVersion": "1.0.0.0",
    "parameters": {
        "accountName": {"value": os.environ["RUNTIME_CONNECTION_ACCOUNT_NAME"]},
        "projectName": {"value": os.environ["RUNTIME_CONNECTION_PROJECT_NAME"]},
        "location": {"value": os.environ["RUNTIME_CONNECTION_LOCATION"]},
        "runtimeConnectionName": {"value": os.environ["RUNTIME_CONNECTION_NAME"]},
        "runtimeDatabaseUrl": {"value": os.environ["RUNTIME_CONNECTION_DATABASE_URL"]},
    },
}
Path(os.environ["RUNTIME_CONNECTION_PARAMETER_FILE"]).write_text(
    json.dumps(payload), encoding="utf-8"
)
PY
unset RUNTIME_CONNECTION_DATABASE_URL

az account set --subscription "$subscription_id"
az deployment group create \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --name "$DEPLOYMENT_NAME" \
  --template-file "$TEMPLATE_FILE" \
  --parameters "@$PARAMETER_FILE" \
  --only-show-errors \
  --output none
cleanup

connection_url="https://management.azure.com/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/${account_name}/projects/${project_name}/connections/${connection_name}?api-version=2025-04-01-preview"
connection_metadata="$(
  az rest \
    --subscription "$subscription_id" \
    --method get \
    --url "$connection_url" \
    --query '{name:name,category:properties.category,auth_type:properties.authType}' \
    --output json
)"
jq -e \
  --arg name "$connection_name" \
  '.name == $name and .category == "CustomKeys" and .auth_type == "CustomKeys"' \
  <<<"$connection_metadata" >/dev/null || {
  echo "Foundry runtime secret connection metadata is incorrect." >&2
  exit 1
}

AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
  azd env set FOUNDRY_RUNTIME_CONNECTION_NAME "$connection_name" \
  --cwd "$FOUNDRY_DIR" --no-prompt >/dev/null

release_id="${FOUNDRY_RELEASE_ID:-manual-runtime-connection}"
release_started_at="${FOUNDRY_RELEASE_STARTED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
jq -n \
  --arg release_id "$release_id" \
  --arg release_started_at "$release_started_at" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg subscription_id "$subscription_id" \
  --arg resource_group "$resource_group" \
  --arg account_name "$account_name" \
  --arg project_name "$project_name" \
  --arg connection_name "$connection_name" \
  '{
    schema_version: 1,
    evidence_type: "component_deployment",
    component: "runtime_connection",
    status: "converged",
    release_id: $release_id,
    release_started_at: $release_started_at,
    generated_at: $generated_at,
    target: {
      subscription_id: $subscription_id,
      resource_group: $resource_group,
      foundry_account: $account_name,
      foundry_project: $project_name
    },
    connection_name: $connection_name,
    category: "CustomKeys",
    auth_type: "CustomKeys",
    key_name: "database_url"
  }' >"$METADATA_FILE"

echo "FOUNDRY_RUNTIME_CONNECTION_NAME=$connection_name"
echo "Foundry runtime secret connection converged without exposing its credential."
