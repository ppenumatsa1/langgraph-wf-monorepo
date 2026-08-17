#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
}

required_env() {
  local name="$1"
  local value
  value="$(get_env "$name")"
  if [[ -z "$value" ]]; then
    echo "Missing required azd environment value: $name" >&2
    exit 1
  fi
  printf '%s' "$value"
}

require_bin az
require_bin azd

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"

resource_group="$(required_env AZURE_RESOURCE_GROUP)"
subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
account_name="$(required_env FOUNDRY_ACCOUNT_NAME)"
project_name="$(required_env FOUNDRY_PROJECT_NAME)"
az account set --subscription "$subscription_id" >/dev/null
appinsights_resource_id="$(get_env APPLICATIONINSIGHTS_RESOURCE_ID)"
if [[ -z "$appinsights_resource_id" ]]; then
  appinsights_resource_id="$(
    az monitor app-insights component show \
      --subscription "$subscription_id" \
      --resource-group "$resource_group" \
      --app "$(required_env APPLICATION_INSIGHTS_NAME)" \
      --query id \
      --output tsv
  )"
fi

connection_url="https://management.azure.com/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/${account_name}/projects/${project_name}/connections/ApplicationInsights?api-version=2025-04-01-preview"
connection_category="$(az rest --method get --url "$connection_url" --query properties.category -o tsv)"
connection_target="$(az rest --method get --url "$connection_url" --query properties.target -o tsv)"
connection_resource_id="$(az rest --method get --url "$connection_url" --query properties.metadata.ResourceId -o tsv)"

if [[ "$connection_category" != "AppInsights" ]] ||
  [[ "${connection_target,,}" != "${appinsights_resource_id,,}" ]] ||
  [[ "${connection_resource_id,,}" != "${appinsights_resource_id,,}" ]]; then
  echo "Foundry project ApplicationInsights connection does not target the configured App Insights resource." >&2
  exit 1
fi

echo "Verified Foundry project ApplicationInsights connection: ${account_name}/${project_name}"
