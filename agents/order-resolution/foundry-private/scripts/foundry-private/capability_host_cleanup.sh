#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

private_require_command az
private_require_command jq
private_require_target

subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(private_azd_value AZURE_RESOURCE_GROUP)"
account_name="$(private_required_env_value FOUNDRY_ACCOUNT_NAME)"
project_name="$(private_required_env_value FOUNDRY_PROJECT_NAME)"
host_name="$(private_required_env_value FOUNDRY_PROJECT_CAPABILITY_HOST_NAME)"
private_validate_identifier FOUNDRY_PROJECT_CAPABILITY_HOST_NAME "$host_name"

host_url="https://management.azure.com/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/${account_name}/projects/${project_name}/capabilityHosts/${host_name}?api-version=2025-06-01"
agents_url="https://management.azure.com/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/${account_name}/projects/${project_name}/capabilityHosts/${host_name}/agents?api-version=2025-06-01"

agents_json="$(az rest --subscription "$subscription_id" --method get --url "$agents_url" --output json)"
mapfile -t agent_ids < <(jq -r '.value[]?.id // empty' <<<"$agents_json")
for agent_id in "${agent_ids[@]}"; do
  az rest --subscription "$subscription_id" --method delete \
    --url "https://management.azure.com${agent_id}?api-version=2025-06-01" \
    --output none
done

az rest --subscription "$subscription_id" --method delete --url "$host_url" --output none
for _ in $(seq 1 30); do
  if ! az rest --subscription "$subscription_id" --method get --url "$host_url" --output none 2>/dev/null; then
    echo "Private capability host and its agents were removed before any account-level cleanup."
    exit 0
  fi
  sleep 10
done

private_die "capability host deletion did not converge within the bounded wait"
