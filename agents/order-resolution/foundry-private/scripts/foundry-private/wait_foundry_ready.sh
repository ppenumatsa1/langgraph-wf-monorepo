#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

private_require_command az
private_require_target

subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(private_azd_value AZURE_RESOURCE_GROUP)"
foundry_account="$(private_required_env_value FOUNDRY_ACCOUNT_NAME)"
capability_host="${foundry_account}@aml_aiagentservice"
capability_host_id="/subscriptions/$subscription_id/resourceGroups/$resource_group/providers/Microsoft.CognitiveServices/accounts/$foundry_account/capabilityHosts/$capability_host"
deadline=$((SECONDS + 1800))

while ((SECONDS < deadline)); do
  account_state="$(az cognitiveservices account show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$foundry_account" \
    --query properties.provisioningState \
    --output tsv)"
  if host_result="$(az resource show \
    --ids "$capability_host_id" \
    --api-version 2025-06-01 \
    --query properties.provisioningState \
    --output tsv 2>&1)"; then
    host_state="$host_result"
  elif [[ "$host_result" == *"ResourceNotFound"* || "$host_result" == *"could not be found"* ]]; then
    host_state=""
  else
    private_die "Foundry capability-host readiness query failed"
  fi

  if [[ "$account_state" == "Succeeded" && "$host_state" == "Succeeded" ]]; then
    echo "Foundry account and account capability host are ready."
    exit 0
  fi
  case "$account_state:$host_state" in
    *Failed*|*Canceled*|*Cancelled*)
      private_die "Foundry readiness failed: account=$account_state capability-host=${host_state:-missing}"
      ;;
  esac
  sleep 10
done

private_die "Foundry account readiness timed out after 1800 seconds"
