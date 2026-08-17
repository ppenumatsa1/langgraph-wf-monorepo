#!/usr/bin/env bash
set -euo pipefail

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
  [[ -n "$value" ]] || {
    echo "Missing AZD environment value: $name" >&2
    exit 1
  }
  printf '%s' "$value"
}

command -v az >/dev/null 2>&1 || {
  echo "Missing required binary: az" >&2
  exit 1
}
command -v azd >/dev/null 2>&1 || {
  echo "Missing required binary: azd" >&2
  exit 1
}

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
foundry_account="$(required_env FOUNDRY_ACCOUNT_NAME)"
foundry_project="$(required_env FOUNDRY_PROJECT_NAME)"
hosted_agent="$(required_env HOSTED_AGENT_NAME)"
identity_name="${foundry_account}-${foundry_project}-${hosted_agent}-AgentIdentity"

az account set --subscription "$subscription_id" >/dev/null
principal_id="$(
  az ad sp list \
    --display-name "$identity_name" \
    --query '[0].id' \
    --output tsv
)"
[[ -n "$principal_id" ]] || {
  echo "Hosted agent identity '$identity_name' was not found." >&2
  exit 1
}
scope="$(
  az cognitiveservices account show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$foundry_account" \
    --query id \
    --output tsv
)"
assignment_count="$(
  az role assignment list \
    --subscription "$subscription_id" \
    --assignee "$principal_id" \
    --role "Cognitive Services OpenAI User" \
    --scope "$scope" \
    --query 'length(@)' \
    --output tsv
)"
if [[ "$assignment_count" == "0" ]]; then
  az role assignment create \
    --subscription "$subscription_id" \
    --assignee-object-id "$principal_id" \
    --assignee-principal-type ServicePrincipal \
    --role "Cognitive Services OpenAI User" \
    --scope "$scope" \
    --output none
fi

echo "Hosted agent RBAC converged: Cognitive Services OpenAI User."
