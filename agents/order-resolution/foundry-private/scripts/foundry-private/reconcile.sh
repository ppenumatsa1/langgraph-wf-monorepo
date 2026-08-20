#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

private_require_command az
private_require_command jq
private_require_target

subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(private_azd_value AZURE_RESOURCE_GROUP)"
foundry_account="$(private_required_env_value FOUNDRY_ACCOUNT_NAME)"
registry_name="$(private_required_env_value AZURE_CONTAINER_REGISTRY_NAME)"
postgres_name="$(private_required_env_value POSTGRES_SERVER_NAME)"
storage_name="$(private_required_env_value STANDARD_AGENT_STORAGE_ACCOUNT_NAME)"
cosmos_name="$(private_required_env_value STANDARD_AGENT_COSMOS_ACCOUNT_NAME)"
search_name="$(private_required_env_value STANDARD_AGENT_SEARCH_NAME)"
monitor_scope_name="$(private_required_env_value AZURE_MONITOR_PRIVATE_LINK_SCOPE_NAME)"

assert_private_endpoint() {
  local resource_id="$1"
  local label="$2"
  local connections
  connections="$(az network private-endpoint-connection list --id "$resource_id" --output json)"
  jq -e 'any(.[]; (.privateLinkServiceConnectionState.status // "") == "Approved")' \
    <<<"$connections" >/dev/null ||
    private_die "$label must have an approved private endpoint connection"
}

assert_public_access_disabled() {
  local resource_json="$1"
  local label="$2"
  local access
  access="$(jq -r '.properties.publicNetworkAccess // .network.publicNetworkAccess // .publicNetworkAccess // empty' <<<"$resource_json")"
  [[ "${access,,}" == "disabled" ]] ||
    private_die "$label public network access must be Disabled"
}

foundry_id="$(az cognitiveservices account show --subscription "$subscription_id" --resource-group "$resource_group" --name "$foundry_account" --query id --output tsv)"
registry_json="$(az acr show --subscription "$subscription_id" --resource-group "$resource_group" --name "$registry_name" --output json)"
postgres_json="$(az postgres flexible-server show --subscription "$subscription_id" --resource-group "$resource_group" --name "$postgres_name" --output json)"
storage_json="$(az storage account show --subscription "$subscription_id" --resource-group "$resource_group" --name "$storage_name" --output json)"
cosmos_json="$(az cosmosdb show --subscription "$subscription_id" --resource-group "$resource_group" --name "$cosmos_name" --output json)"
search_json="$(az search service show --subscription "$subscription_id" --resource-group "$resource_group" --name "$search_name" --output json)"
monitor_scope_json="$(az resource show --subscription "$subscription_id" --resource-group "$resource_group" --name "$monitor_scope_name" --resource-type Microsoft.Insights/privateLinkScopes --api-version 2021-07-01-preview --output json)"

assert_public_access_disabled "$registry_json" ACR
assert_public_access_disabled "$postgres_json" PostgreSQL
assert_public_access_disabled "$storage_json" Private-storage
assert_public_access_disabled "$cosmos_json" Private-Cosmos
assert_public_access_disabled "$search_json" Private-search
[[ "$(az cognitiveservices account show --subscription "$subscription_id" --resource-group "$resource_group" --name "$foundry_account" --query properties.publicNetworkAccess --output tsv)" == "Disabled" ]] ||
  private_die "Foundry public network access must be Disabled"

assert_private_endpoint "$foundry_id" Foundry
assert_private_endpoint "$(jq -r '.id' <<<"$registry_json")" ACR
assert_private_endpoint "$(jq -r '.id' <<<"$postgres_json")" PostgreSQL
assert_private_endpoint "$(jq -r '.id' <<<"$storage_json")" Private-storage
assert_private_endpoint "$(jq -r '.id' <<<"$cosmos_json")" Private-Cosmos
assert_private_endpoint "$(jq -r '.id' <<<"$search_json")" Private-search
assert_private_endpoint "$(jq -r '.id' <<<"$monitor_scope_json")" Azure-Monitor-private-link-scope

runner_name="$(private_runner_name)"
runner_group="$(private_runner_resource_group)"
runner_power="$(az vm get-instance-view --subscription "$subscription_id" --resource-group "$runner_group" --name "$runner_name" --query "instanceView.statuses[?code=='PowerState/running'] | length(@)" --output tsv)"
[[ "$runner_power" == "1" ]] || private_die "private runner VM is not running"

echo "Private infrastructure reconciliation passed without changing Azure resources."
