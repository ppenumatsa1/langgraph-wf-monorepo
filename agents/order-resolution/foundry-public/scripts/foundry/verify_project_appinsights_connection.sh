#!/usr/bin/env bash
set -euo pipefail

require_env_value() {
  local key="$1"
  local value
  value="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$key")"
  if [[ -z "$value" ]]; then
    echo "Missing required azd environment value: $key" >&2
    exit 1
  fi
  printf '%s\n' "$value"
}

command -v az >/dev/null 2>&1 || {
  echo "Missing required binary: az" >&2
  exit 1
}
command -v azd >/dev/null 2>&1 || {
  echo "Missing required binary: azd" >&2
  exit 1
}
command -v jq >/dev/null 2>&1 || {
  echo "Missing required binary: jq" >&2
  exit 1
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="${FOUNDRY_DIR:-$ROOT_DIR/infra/foundry-hosted}"
if [[ ! -f "$FOUNDRY_DIR/azure.yaml" ]]; then
  echo "Unable to locate Foundry AZD project at $FOUNDRY_DIR" >&2
  exit 1
fi
cd "$FOUNDRY_DIR"

resource_group="$(require_env_value AZURE_RESOURCE_GROUP)"
subscription_id="$(require_env_value AZURE_SUBSCRIPTION_ID)"
account_name="$(require_env_value FOUNDRY_ACCOUNT_NAME)"
project_name="$(require_env_value FOUNDRY_PROJECT_NAME)"
appinsights_resource_id="$(require_env_value APPLICATIONINSIGHTS_RESOURCE_ID)"
[[ "$subscription_id" == "7df95e88-701c-4693-af77-3159f83b558d" ]] &&
  [[ "$resource_group" == "rg-langgraph-ora-foundry-public" ]] || {
  echo "Application Insights connection verification requires the canonical public target." >&2
  exit 1
}

az account set --subscription "$subscription_id"
connection_url="https://management.azure.com/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/${account_name}/projects/${project_name}/connections/ApplicationInsights?api-version=2025-04-01-preview"
connection_category="$(az rest --subscription "$subscription_id" --method get --url "$connection_url" --query properties.category -o tsv)"
connection_target="$(az rest --subscription "$subscription_id" --method get --url "$connection_url" --query properties.target -o tsv)"
connection_resource_id="$(az rest --subscription "$subscription_id" --method get --url "$connection_url" --query properties.metadata.ResourceId -o tsv)"

if [[ "$connection_category" != "AppInsights" ]] ||
  [[ "${connection_target,,}" != "${appinsights_resource_id,,}" ]] ||
  [[ "${connection_resource_id,,}" != "${appinsights_resource_id,,}" ]]; then
  echo "Foundry project ApplicationInsights connection does not target the configured App Insights resource." >&2
  exit 1
fi

evidence_file="${APPINSIGHTS_CONNECTION_EVIDENCE_FILE:-$ROOT_DIR/backend/.foundry/results/appinsights-connection-evidence.json}"
release_id="${FOUNDRY_RELEASE_ID:-manual-appinsights-verification}"
release_started_at="${FOUNDRY_RELEASE_STARTED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
mkdir -p "$(dirname "$evidence_file")"
jq -n \
  --arg release_id "$release_id" \
  --arg release_started_at "$release_started_at" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg subscription_id "$subscription_id" \
  --arg account_name "$account_name" \
  --arg project_name "$project_name" \
  --arg resource_id "$appinsights_resource_id" \
  '{
    schema_version: 1,
    evidence_type: "appinsights_connection",
    status: "passed",
    release_id: $release_id,
    release_started_at: $release_started_at,
    generated_at: $generated_at,
    subscription_id: $subscription_id,
    foundry_account: $account_name,
    foundry_project: $project_name,
    application_insights_resource_id: $resource_id
  }' >"$evidence_file"

echo "Verified Foundry project ApplicationInsights connection: ${account_name}/${project_name}"
echo "Evidence written to ${evidence_file}."
