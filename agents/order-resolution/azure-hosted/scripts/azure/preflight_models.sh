#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR"
EVIDENCE_FILE="${FOUNDRY_MODEL_PREFLIGHT_EVIDENCE_FILE:-$ROOT_DIR/.artifacts/releases/${AZURE_RELEASE_ID:?AZURE_RELEASE_ID is required}/evidence/model-preflight.json}"

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

require_bin az
require_bin azd
require_bin jq

"$ROOT_DIR/scripts/azure/ensure_azd_defaults.sh"

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
location="$(required_env AZURE_LOCATION)"
foundry_account="$(required_env FOUNDRY_ACCOUNT_NAME)"
chat_deployment="$(required_env FOUNDRY_MODEL_DEPLOYMENT_NAME)"
embeddings_deployment="$(required_env FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME)"
evaluation_deployment="$(required_env FOUNDRY_EVAL_MODEL)"

[[ "$subscription_id" == "7df95e88-701c-4693-af77-3159f83b558d" ]] || {
  echo "Model preflight requires the canonical public subscription." >&2
  exit 1
}
[[ "$resource_group" == "rg-langgraph-ora-azure-hosted" ]] || {
  echo "Model preflight requires the canonical public resource group." >&2
  exit 1
}
[[ "${location,,}" == "eastus2" ]] || {
  echo "Model preflight requires the canonical eastus2 location." >&2
  exit 1
}
[[ "$chat_deployment" == "order-resolution-gpt-4-1-mini" ]] || {
  echo "Unexpected Order Resolution chat deployment: $chat_deployment" >&2
  exit 1
}
[[ "$embeddings_deployment" == "order-resolution-text-embedding-3-small" ]] || {
  echo "Unexpected Order Resolution embeddings deployment: $embeddings_deployment" >&2
  exit 1
}
[[ "$evaluation_deployment" == "order-resolution-gpt-4-1-mini-evaluation" ]] || {
  echo "Unexpected Order Resolution evaluator deployment: $evaluation_deployment" >&2
  exit 1
}

az account set --subscription "$subscription_id"
deployments_json="$(
  az cognitiveservices account deployment list \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$foundry_account" \
    --output json
)"
usage_json="$(
  az cognitiveservices usage list \
    --subscription "$subscription_id" \
    --location "$location" \
    --output json
)"

models_json='[]'
quota_json='[]'
check_deployment() {
  local purpose="$1"
  local deployment_name="$2"
  local expected_model="$3"
  local deployment matches quota_matches quota_match_count
  local state live_model live_version sku_name capacity

  matches="$(jq -c --arg name "$deployment_name" '[.[] | select(.name == $name)]' <<<"$deployments_json")"
  if [[ "$(jq 'length' <<<"$matches")" -ne 1 ]]; then
    echo "Expected exactly one live deployment named $deployment_name." >&2
    exit 1
  fi
  deployment="$(jq -c '.[0]' <<<"$matches")"
  state="$(jq -r '.properties.provisioningState // .provisioningState // empty' <<<"$deployment")"
  live_model="$(jq -r '.properties.model.name // .model.name // empty' <<<"$deployment")"
  live_version="$(jq -r '.properties.model.version // .model.version // empty' <<<"$deployment")"
  sku_name="$(jq -r '.sku.name // empty' <<<"$deployment")"
  capacity="$(jq -r '.sku.capacity // 0' <<<"$deployment")"

  [[ "${state,,}" == "succeeded" ]] || {
    echo "Deployment $deployment_name is not provisioned successfully (state=${state:-missing})." >&2
    exit 1
  }
  [[ "${live_model,,}" == "${expected_model,,}" ]] || {
    echo "Deployment $deployment_name uses $live_model, expected $expected_model." >&2
    exit 1
  }
  [[ -n "$sku_name" && "$capacity" =~ ^[0-9]+$ && "$capacity" -gt 0 ]] || {
    echo "Deployment $deployment_name does not expose a valid live SKU and capacity." >&2
    exit 1
  }

  quota_matches="$(
    jq -c --arg model "$expected_model" '
      ($model | ascii_downcase | gsub("[^a-z0-9]"; "")) as $needle
      | [
          .[]
          | select(
              (
                ((.name.value // "") + " " + (.name.localizedValue // ""))
                | ascii_downcase
                | gsub("[^a-z0-9]"; "")
              )
              | contains($needle)
            )
          | {
              name: (.name.value // .name.localizedValue // "unknown"),
              current_value: (.currentValue // 0),
              limit: (.limit // 0),
              unit: (.unit // "")
            }
        ]
    ' <<<"$usage_json"
  )"
  quota_match_count="$(jq 'length' <<<"$quota_matches")"
  [[ "$quota_match_count" -gt 0 ]] || {
    echo "No quota record was returned for live model $expected_model in $location." >&2
    exit 1
  }
  jq -e 'all(.[]; (.current_value | tonumber) <= (.limit | tonumber))' \
    <<<"$quota_matches" >/dev/null || {
    echo "Quota usage exceeds the reported limit for $expected_model." >&2
    exit 1
  }

  models_json="$(
    jq -c \
      --arg purpose "$purpose" \
      --arg deployment_name "$deployment_name" \
      --arg model "$live_model" \
      --arg version "$live_version" \
      --arg sku "$sku_name" \
      --argjson capacity "$capacity" \
      '. + [{
        purpose: $purpose,
        deployment_name: $deployment_name,
        model: $model,
        version: $version,
        live_sku: $sku,
        live_capacity: $capacity
      }]' <<<"$models_json"
  )"
  quota_json="$(
    jq -c \
      --arg purpose "$purpose" \
      --arg model "$expected_model" \
      --argjson records "$quota_matches" \
      '. + [{purpose: $purpose, model: $model, records: $records}]' <<<"$quota_json"
  )"
}

check_deployment chat "$chat_deployment" gpt-4.1-mini
check_deployment embeddings "$embeddings_deployment" text-embedding-3-small
check_deployment evaluator "$evaluation_deployment" gpt-4.1-mini

release_id="$AZURE_RELEASE_ID"
release_started_at="${AZURE_RELEASE_STARTED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
mkdir -p "$(dirname "$EVIDENCE_FILE")"
jq -n \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg release_id "$release_id" \
  --arg release_started_at "$release_started_at" \
  --arg subscription_id "$subscription_id" \
  --arg resource_group "$resource_group" \
  --arg location "$location" \
  --arg foundry_account "$foundry_account" \
  --argjson deployments "$models_json" \
  --argjson quota "$quota_json" \
  '{
    schema_version: 1,
    evidence_type: "model_preflight",
    status: "passed",
    release_id: $release_id,
    release_started_at: $release_started_at,
    generated_at: $generated_at,
    target: {
      subscription_id: $subscription_id,
      resource_group: $resource_group,
      location: $location,
      foundry_account: $foundry_account
    },
    deployments: $deployments,
    quota: $quota,
    mutation_performed: false
  }' >"$EVIDENCE_FILE"

echo "Foundry model deployment and quota preflight passed without changing live deployments."
echo "Evidence written to ${EVIDENCE_FILE}."
