#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
ROLE_NAME="Cognitive Services OpenAI User"

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

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
foundry_account="$(required_env FOUNDRY_ACCOUNT_NAME)"
[[ "$subscription_id" == "7df95e88-701c-4693-af77-3159f83b558d" ]] &&
  [[ "$resource_group" == "rg-langgraph-ora-foundry-public" ]] || {
  echo "Hosted-agent RBAC convergence requires the canonical public target." >&2
  exit 1
}
principal_id="${HOSTED_AGENT_PRINCIPAL_ID:-$(get_env AGENT_ORDER_RESOLUTION_HOSTED_PRINCIPAL_ID)}"
[[ -n "$principal_id" ]] || {
  echo "Hosted-agent principal ID is required for RBAC convergence." >&2
  exit 1
}

az account set --subscription "$subscription_id"
scope="$(
  az cognitiveservices account show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$foundry_account" \
    --query id \
    --output tsv
)"
[[ -n "$scope" ]] || {
  echo "Unable to resolve the Foundry account resource ID." >&2
  exit 1
}

assignment_exists() {
  local assignments
  assignments="$(
    az role assignment list \
      --subscription "$subscription_id" \
      --assignee-object-id "$principal_id" \
      --role "$ROLE_NAME" \
      --scope "$scope" \
      --fill-principal-name false \
      --output json
  )"
  jq -e --arg scope "${scope,,}" '
    any(.[]; ((.scope // "") | ascii_downcase) == $scope)
  ' <<<"$assignments" >/dev/null
}

for attempt in $(seq 1 "${FOUNDRY_RBAC_MAX_ATTEMPTS:-18}"); do
  if assignment_exists; then
    echo "HOSTED_AGENT_RBAC_ROLE=$ROLE_NAME"
    echo "HOSTED_AGENT_RBAC_SCOPE=$scope"
    echo "Hosted-agent RBAC converged at the Foundry account scope."
    exit 0
  fi
  set +e
  create_output="$(
    az role assignment create \
      --subscription "$subscription_id" \
      --assignee-object-id "$principal_id" \
      --assignee-principal-type ServicePrincipal \
      --role "$ROLE_NAME" \
      --scope "$scope" \
      --output none 2>&1
  )"
  create_status=$?
  set -e
  if [[ $create_status -ne 0 ]] &&
    ! grep -Eqi 'RoleAssignmentExists|PrincipalNotFound|does not exist in the directory' \
      <<<"$create_output"; then
    echo "$create_output" >&2
    exit "$create_status"
  fi
  echo "Awaiting hosted-agent RBAC propagation (${attempt}/${FOUNDRY_RBAC_MAX_ATTEMPTS:-18})."
  sleep "${FOUNDRY_RBAC_POLL_SECONDS:-10}"
done

echo "Hosted-agent RBAC did not converge within the bounded wait." >&2
exit 1
