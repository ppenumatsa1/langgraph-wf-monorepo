#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
TEMPLATE="$FOUNDRY_DIR/iac/runtime-secret-connection.bicep"
readonly EXPECTED_CONNECTION_NAME="underwritingruntimesecrets"

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

for binary in az azd jq python3; do
  command -v "$binary" >/dev/null 2>&1 || {
    echo "Missing required binary: $binary" >&2
    exit 1
  }
done
[[ -r "$TEMPLATE" ]] || {
  echo "Missing Underwriting runtime-secret connection template." >&2
  exit 1
}

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
location="$(required_env AZURE_LOCATION)"
account_name="$(required_env FOUNDRY_ACCOUNT_NAME)"
project_name="$(required_env FOUNDRY_PROJECT_NAME)"
postgres_server_name="$(required_env POSTGRES_SERVER_NAME)"
runtime_database_url="$(required_env RUNTIME_DATABASE_URL)"
database_url="$(required_env DATABASE_URL)"
connection_name="$(required_env FOUNDRY_RUNTIME_CONNECTION_NAME)"

[[ "$connection_name" == "$EXPECTED_CONNECTION_NAME" ]] || {
  echo "FOUNDRY_RUNTIME_CONNECTION_NAME must be ${EXPECTED_CONNECTION_NAME}." >&2
  exit 1
}
[[ "$database_url" == "$runtime_database_url" ]] || {
  echo "DATABASE_URL and RUNTIME_DATABASE_URL must match before connection convergence." >&2
  exit 1
}

POSTGRES_SERVER_NAME="$postgres_server_name" \
RUNTIME_DATABASE_URL="$runtime_database_url" \
  python3 - <<'PY'
import os
import sys
from urllib.parse import parse_qs, urlsplit

parsed = urlsplit(os.environ["RUNTIME_DATABASE_URL"])
expected_host = f'{os.environ["POSTGRES_SERVER_NAME"]}.postgres.database.azure.com'
if parsed.scheme != "postgresql+psycopg":
    sys.exit("RUNTIME_DATABASE_URL must use the postgresql+psycopg driver.")
if parsed.hostname != expected_host or parsed.port != 5432:
    sys.exit("RUNTIME_DATABASE_URL does not target the selected PostgreSQL server.")
if not parsed.username or not parsed.password:
    sys.exit("RUNTIME_DATABASE_URL must contain the runtime credential.")
if parse_qs(parsed.query).get("sslmode") != ["require"]:
    sys.exit("RUNTIME_DATABASE_URL must require TLS.")
PY

az account set --subscription "$subscription_id" >/dev/null
active_subscription="$(az account show --query id --output tsv)"
[[ "$active_subscription" == "$subscription_id" ]] || {
  echo "Azure CLI did not select the requested subscription." >&2
  exit 1
}
actual_location="$(
  az group show \
    --subscription "$subscription_id" \
    --name "$resource_group" \
    --query location \
    --output tsv
)"
[[ "$actual_location" == "$location" ]] || {
  echo "Selected resource group location does not match AZURE_LOCATION." >&2
  exit 1
}

emit_parameters() {
  FOUNDRY_ACCOUNT_NAME="$account_name" \
  FOUNDRY_PROJECT_NAME="$project_name" \
  AZURE_LOCATION="$location" \
  FOUNDRY_RUNTIME_CONNECTION_NAME="$connection_name" \
  RUNTIME_DATABASE_URL="$runtime_database_url" \
    python3 - <<'PY'
import json
import os

print(
    json.dumps(
        {
            "$schema": (
                "https://schema.management.azure.com/schemas/"
                "2019-04-01/deploymentParameters.json#"
            ),
            "contentVersion": "1.0.0.0",
            "parameters": {
                "foundryAccountName": {"value": os.environ["FOUNDRY_ACCOUNT_NAME"]},
                "foundryProjectName": {"value": os.environ["FOUNDRY_PROJECT_NAME"]},
                "location": {"value": os.environ["AZURE_LOCATION"]},
                "runtimeConnectionName": {
                    "value": os.environ["FOUNDRY_RUNTIME_CONNECTION_NAME"]
                },
                "runtimeDatabaseUrl": {"value": os.environ["RUNTIME_DATABASE_URL"]},
            },
        }
    )
)
PY
}

deployment_suffix="${RELEASE_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
deployment_suffix="$(printf '%s' "$deployment_suffix" | tr -c '[:alnum:]_.-' '-')"
deployment_name="underwriting-runtime-secret-${deployment_suffix:0:35}"

emit_parameters |
  az deployment group create \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$deployment_name" \
    --template-file "$TEMPLATE" \
    --parameters @/dev/stdin \
    --mode Incremental \
    --only-show-errors \
    --output none

connection_url="https://management.azure.com/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/${account_name}/projects/${project_name}/connections/${connection_name}?api-version=2025-04-01-preview"
connection_metadata="$(
  az rest \
    --method get \
    --url "$connection_url" \
    --query '{category:properties.category,authType:properties.authType,target:properties.target}' \
    --output json
)"
jq -e '
  .category == "CustomKeys"
  and .authType == "CustomKeys"
  and .target == "https://underwriting-runtime-secrets.local"
' >/dev/null <<<"$connection_metadata" || {
  echo "Underwriting runtime-secret connection metadata verification failed." >&2
  exit 1
}

AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
  azd env set FOUNDRY_RUNTIME_CONNECTION_NAME "$connection_name" \
  --cwd "$FOUNDRY_DIR" --no-prompt >/dev/null

unset database_url runtime_database_url
echo "Converged Underwriting Foundry project CustomKeys runtime-secret connection."
