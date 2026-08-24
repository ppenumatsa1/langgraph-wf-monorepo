#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

for command in az jq python3; do
  private_require_command "$command"
done
private_require_target
release_id="$(private_release_id)"
release_dir="$(private_release_dir)"

"$SCRIPT_DIR/runner_exec.sh" verify_runtime evidence/private-runtime-verification.json
runtime_details="$(jq -c '.details' "$release_dir/evidence/private-runtime-verification.json")"

subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(private_azd_value AZURE_RESOURCE_GROUP)"
location="$(private_azd_value AZURE_LOCATION)"
foundry_account="$(private_required_env_value FOUNDRY_ACCOUNT_NAME)"
registry_name="$(private_required_env_value AZURE_CONTAINER_REGISTRY_NAME)"
postgres_name="$(private_required_env_value POSTGRES_SERVER_NAME)"
storage_name="$(private_required_env_value STANDARD_AGENT_STORAGE_ACCOUNT_NAME)"
cosmos_name="$(private_required_env_value STANDARD_AGENT_COSMOS_ACCOUNT_NAME)"
search_name="$(private_required_env_value STANDARD_AGENT_SEARCH_NAME)"
monitor_scope_name="$(private_required_env_value AZURE_MONITOR_PRIVATE_LINK_SCOPE_NAME)"
environment_id="$(private_required_env_value AZURE_CONTAINER_APPS_ENVIRONMENT_ID)"
backend_name="$(private_required_env_value BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(private_required_env_value FRONTEND_CONTAINER_APP_NAME)"
appinsights_name="$(private_required_env_value APPLICATION_INSIGHTS_NAME)"

assert_private_endpoint() {
  local resource_id="$1"
  local label="$2"
  local connections
  connections="$(az network private-endpoint-connection list --id "$resource_id" --output json)"
  jq -e 'any(.[]; (.properties.privateLinkServiceConnectionState.status // "") == "Approved")' \
    <<<"$connections" >/dev/null ||
    private_die "$label is missing an approved private endpoint"
}

assert_public_access_disabled() {
  local resource_json="$1"
  local label="$2"
  local access
  access="$(jq -r '.properties.publicNetworkAccess // .network.publicNetworkAccess // .publicNetworkAccess // empty' <<<"$resource_json")"
  [[ "${access,,}" == "disabled" ]] ||
    private_die "$label public network access must be Disabled"
}

foundry_json="$(az cognitiveservices account show --subscription "$subscription_id" --resource-group "$resource_group" --name "$foundry_account" --output json)"
registry_json="$(az acr show --subscription "$subscription_id" --resource-group "$resource_group" --name "$registry_name" --output json)"
postgres_json="$(az postgres flexible-server show --subscription "$subscription_id" --resource-group "$resource_group" --name "$postgres_name" --output json)"
storage_json="$(az storage account show --subscription "$subscription_id" --resource-group "$resource_group" --name "$storage_name" --output json)"
cosmos_json="$(az cosmosdb show --subscription "$subscription_id" --resource-group "$resource_group" --name "$cosmos_name" --output json)"
search_json="$(az search service show --subscription "$subscription_id" --resource-group "$resource_group" --name "$search_name" --output json)"
monitor_scope_json="$(az resource show --subscription "$subscription_id" --resource-group "$resource_group" --name "$monitor_scope_name" --resource-type Microsoft.Insights/privateLinkScopes --api-version 2021-07-01-preview --output json)"
environment_json="$(az containerapp env show --subscription "$subscription_id" --ids "$environment_id" --output json)"
appinsights_json="$(az monitor app-insights component show --subscription "$subscription_id" --resource-group "$resource_group" --app "$appinsights_name" --output json)"

assert_public_access_disabled "$foundry_json" Foundry
assert_public_access_disabled "$registry_json" ACR
assert_public_access_disabled "$postgres_json" PostgreSQL
assert_public_access_disabled "$storage_json" Private-storage
assert_public_access_disabled "$cosmos_json" Private-Cosmos
assert_public_access_disabled "$search_json" Private-search
[[ "$(jq -r '.properties.vnetConfiguration.infrastructureSubnetId // empty' <<<"$environment_json")" != "" ]] ||
  private_die "Container Apps environment must use the private infrastructure subnet"
[[ "$(jq -r '.publicNetworkAccessForIngestion // .properties.publicNetworkAccessForIngestion // empty' <<<"$appinsights_json")" == "Disabled" ]] ||
  private_die "Application Insights ingestion public network access must be Disabled"
[[ "$(jq -r '.publicNetworkAccessForQuery // .properties.publicNetworkAccessForQuery // empty' <<<"$appinsights_json")" == "Disabled" ]] ||
  private_die "Application Insights query public network access must be Disabled"

assert_private_endpoint "$(jq -r '.id' <<<"$foundry_json")" Foundry
assert_private_endpoint "$(jq -r '.id' <<<"$registry_json")" ACR
assert_private_endpoint "$(jq -r '.id' <<<"$postgres_json")" PostgreSQL
assert_private_endpoint "$(jq -r '.id' <<<"$storage_json")" Private-storage
assert_private_endpoint "$(jq -r '.id' <<<"$cosmos_json")" Private-Cosmos
assert_private_endpoint "$(jq -r '.id' <<<"$search_json")" Private-search
assert_private_endpoint "$(jq -r '.id' <<<"$monitor_scope_json")" Azure-Monitor-private-link-scope

container_apps="$(az containerapp list --subscription "$subscription_id" --resource-group "$resource_group" --output json)"
jq -e --arg backend "$backend_name" --arg frontend "$frontend_name" \
  '([.[].name] | sort) == ([$backend,$frontend] | sort)' <<<"$container_apps" >/dev/null ||
  private_die "private resource group must contain exactly the expected two Container Apps"

connection_url="https://management.azure.com/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/${foundry_account}/connections/ApplicationInsights?api-version=2025-04-01-preview"
connection_json="$(az rest --subscription "$subscription_id" --method get --url "$connection_url" --output json)"
jq -e '.properties.category == "AppInsights" and (.properties.target | type == "string" and length > 0)' \
  <<<"$connection_json" >/dev/null ||
  private_die "private Foundry project Application Insights connection is missing or invalid"

generated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
jq -n \
  --arg release_id "$release_id" \
  --arg generated_at "$generated_at" \
  --arg subscription_id "$subscription_id" \
  --arg resource_group "$resource_group" \
  --arg location "$location" \
  --arg backend "$backend_name" \
  --arg frontend "$frontend_name" \
  --argjson runtime "$runtime_details" \
  '{schema_version:1,evidence_type:"deployment_verification",status:"passed",release_id:$release_id,generated_at:$generated_at,target:{subscription_id:$subscription_id,resource_group:$resource_group,location:$location},container_apps:{backend:$backend,frontend:$frontend,count:2,backend_external_ingress:false,frontend_external_ingress:true,private_infrastructure_subnet:true},public_access:{foundry:"Disabled",acr:"Disabled",postgres:"Disabled",storage:"Disabled",cosmos:"Disabled",search:"Disabled",appinsights_ingestion:"Disabled",appinsights_query:"Disabled"},private_endpoints:"approved",runtime:$runtime}' |
  python3 "$SCRIPT_DIR/write_artifact.py" --release-id "$release_id" --relative-path evidence/deployment-verification.json

jq -n \
  --arg release_id "$release_id" \
  --arg generated_at "$generated_at" \
  --arg target "$(jq -r '.properties.target' <<<"$connection_json")" \
  '{schema_version:1,evidence_type:"appinsights_connection",status:"passed",release_id:$release_id,generated_at:$generated_at,connection_name:"ApplicationInsights",target:$target,private_network:true}' |
  python3 "$SCRIPT_DIR/write_artifact.py" --release-id "$release_id" --relative-path evidence/appinsights-connection.json
