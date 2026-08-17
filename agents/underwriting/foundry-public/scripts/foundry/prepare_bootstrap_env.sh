#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

get_env() {
  local value
  if value="$(
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
      azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null
  )"; then
    printf '%s' "$value"
  fi
}

set_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env set "$1" "$2" --cwd "$FOUNDRY_DIR" --no-prompt >/dev/null
}

required_env() {
  local name="$1"
  local value
  value="$(get_env "$name")"
  if [[ -z "$value" ]]; then
    echo "Missing AZD environment value: $name" >&2
    exit 1
  fi
  printf '%s' "$value"
}

set_default() {
  local name="$1"
  local value="$2"
  if [[ -z "$(get_env "$name")" ]]; then
    set_env "$name" "$value"
  fi
}

for command in azd curl sha256sum; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required binary: $command" >&2
    exit 1
  }
done

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
required_env AZURE_LOCATION >/dev/null
name_prefix="$(required_env NAME_PREFIX)"
normalized_prefix="$(printf '%s' "$name_prefix" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')"
if [[ ${#normalized_prefix} -lt 3 || ${#normalized_prefix} -gt 20 ]]; then
  echo "NAME_PREFIX must normalize to 3-20 lowercase alphanumeric characters." >&2
  exit 1
fi

resource_name_suffix="$(printf '%s' "${subscription_id}/${resource_group}" | sha256sum | cut -c1-8)"
resource_name_base="${normalized_prefix:0:12}${resource_name_suffix}"

set_env INFRASTRUCTURE_MODE bootstrap
set_env NAME_PREFIX "$normalized_prefix"
operator_ip="$(get_env POSTGRES_OPERATOR_IP)"
if [[ -z "$operator_ip" ]]; then
  operator_ip="$(curl --fail --silent --show-error --max-time 10 -4 https://api.ipify.org)"
  set_env POSTGRES_OPERATOR_IP "$operator_ip"
fi
if [[ ! "$operator_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  echo "POSTGRES_OPERATOR_IP must be a public IPv4 address." >&2
  exit 1
fi
set_default RESOURCE_NAME_SUFFIX "$resource_name_suffix"
set_default FOUNDRY_ACCOUNT_NAME "${resource_name_base}ai"
set_default FOUNDRY_PROJECT_NAME underwriting
set_default FOUNDRY_CUSTOM_SUBDOMAIN_NAME "$(required_env FOUNDRY_ACCOUNT_NAME)"
set_default HOSTED_AGENT_NAME underwriting-hosted
set_default FOUNDRY_RUNTIME_CONNECTION_NAME underwritingruntimesecrets
set_default FOUNDRY_MODEL_DEPLOYMENT_NAME underwriting-gpt-4-1-mini
set_default FOUNDRY_MODEL_FORMAT OpenAI
set_default FOUNDRY_MODEL_NAME gpt-4.1-mini
set_default FOUNDRY_MODEL_VERSION 2025-04-14
set_default FOUNDRY_MODEL_SKU_NAME DataZoneStandard
set_default FOUNDRY_MODEL_CAPACITY 1500
set_default FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME underwriting-text-embedding-3-small
set_default FOUNDRY_EMBEDDINGS_MODEL_VERSION 1
set_default FOUNDRY_EMBEDDINGS_MODEL_CAPACITY 120
set_default FOUNDRY_EVAL_MODEL underwriting-gpt-4-1-mini-evaluation
set_default FOUNDRY_EVALUATION_MODEL_CAPACITY 250
set_default FOUNDRY_RAI_POLICY_NAME Microsoft.Default
set_default POSTGRES_DATABASE underwriting
set_default POSTGRES_ADMIN_USERNAME pgadmin
set_default POSTGRES_RUNTIME_USERNAME underwriting_runtime
set_default POSTGRES_SERVER_NAME "${resource_name_base}pg"
set_default POSTGRES_SERVER_LOCATION "$(required_env AZURE_LOCATION)"
set_default CONTAINER_REGISTRY_NAME "${resource_name_base}acr"
set_default LOG_ANALYTICS_WORKSPACE_NAME "${resource_name_base}-log"
set_default APPLICATION_INSIGHTS_NAME "${resource_name_base}-ai"
set_default CONTAINER_APPS_ENVIRONMENT_NAME "${resource_name_base}-cae"
set_default BACKEND_CONTAINER_APP_NAME "${resource_name_base}-backend"
set_default FRONTEND_CONTAINER_APP_NAME "${resource_name_base}-frontend"
set_default PUBLIC_BACKEND_MANAGED_IDENTITY_NAME "${resource_name_base}-backend-mi"
set_default PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME "${resource_name_base}-frontend-mi"
set_default BACKEND_IMAGE_REPOSITORY underwriting-public-backend
set_default FRONTEND_IMAGE_REPOSITORY underwriting-public-frontend
set_default EVALUATION_STORAGE_ACCOUNT_NAME "${resource_name_base}eval"
set_default BOOTSTRAP_RUNTIME_DATABASE_URL bootstrap-pending

echo "Prepared the selected AZD environment for portable bootstrap mode."
echo "Set POSTGRES_ADMIN_PASSWORD and POSTGRES_HOSTED_PASSWORD securely before credential provisioning."
