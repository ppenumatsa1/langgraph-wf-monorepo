#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

for command in mktemp openssl sha256sum ssh-keygen tr; do
  private_require_command "$command"
done
private_require_target

subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(private_azd_value AZURE_RESOURCE_GROUP)"
location="$(private_azd_value AZURE_LOCATION)"
name_prefix="$(private_required_env_value NAME_PREFIX)"
normalized_prefix="$(printf '%s' "$name_prefix" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')"
[[ "$normalized_prefix" =~ ^[a-z][a-z0-9]{2,14}$ ]] ||
  private_die "NAME_PREFIX must normalize to 3-15 lowercase alphanumeric characters"

suffix="$(printf '%s' "${subscription_id}/${resource_group}" | sha256sum | cut -c1-8)"
name_base="${normalized_prefix}${suffix}"
[[ ${#name_base} -le 23 ]] ||
  private_die "private derived resource-name base is unexpectedly long"

set_default() {
  local key="$1"
  local value="$2"
  if private_azd_optional_value "$key" >/dev/null; then
    return
  fi
  private_azd_set "$key" "$value"
}

set_sensitive_default() {
  local key="$1"
  local environment_key value temp_dir
  case "$key" in
    POSTGRES_ADMIN_PASSWORD) environment_key="FOUNDRY_PRIVATE_POSTGRES_ADMIN_PASSWORD" ;;
    PRIVATE_RUNNER_SSH_PUBLIC_KEY) environment_key="FOUNDRY_PRIVATE_RUNNER_SSH_PUBLIC_KEY" ;;
    *) private_die "unsupported private bootstrap secret key: $key" ;;
  esac
  if private_azd_optional_value "$key" >/dev/null; then
    return
  fi
  value="${!environment_key:-}"
  if [[ -z "$value" ]]; then
    case "$key" in
      POSTGRES_ADMIN_PASSWORD)
        value="Lg!$(openssl rand -hex 24)"
        ;;
      PRIVATE_RUNNER_SSH_PUBLIC_KEY)
        temp_dir="$(mktemp -d)"
        chmod 700 "$temp_dir"
        ssh-keygen -q -t ed25519 -N '' -C 'foundry-private-run-command-only' \
          -f "$temp_dir/runner" >/dev/null
        value="$(tr -d '\r\n' <"$temp_dir/runner.pub")"
        rm -f -- "$temp_dir/runner" "$temp_dir/runner.pub"
        rmdir "$temp_dir"
        ;;
    esac
  fi
  [[ -n "$value" && "$value" != *$'\n'* && "$value" != *$'\r'* ]] ||
    private_die "$key must be a single generated or supplied value"
  private_azd_set "$key" "$value"
}

set_default INFRASTRUCTURE_MODE bootstrap
set_default FOUNDRY_ACCOUNT_NAME "${name_base}ai"
set_default FOUNDRY_PROJECT_NAME order-resolution-private
set_default FOUNDRY_CUSTOM_SUBDOMAIN_NAME "$(private_required_env_value FOUNDRY_ACCOUNT_NAME)"
set_default HOSTED_AGENT_NAME order-resolution-hosted
set_default FOUNDRY_RUNTIME_CONNECTION_NAME orderresolutionprivateruntimesecrets
set_default FOUNDRY_MODEL_DEPLOYMENT_NAME order-resolution-private-gpt-4-1-mini
set_default FOUNDRY_MODEL_FORMAT OpenAI
set_default FOUNDRY_MODEL_NAME gpt-4.1-mini
set_default FOUNDRY_MODEL_VERSION 2025-04-14
set_default FOUNDRY_MODEL_SKU_NAME Standard
set_default FOUNDRY_MODEL_CAPACITY 50
set_default FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME order-resolution-private-text-embedding-3-small
set_default FOUNDRY_EMBEDDINGS_MODEL_VERSION 1
set_default FOUNDRY_EMBEDDINGS_MODEL_CAPACITY 10
set_default FOUNDRY_EVAL_MODEL order-resolution-private-gpt-4-1-mini-evaluation
set_default FOUNDRY_EVALUATION_MODEL_CAPACITY 50
set_default FOUNDRY_RAI_POLICY_NAME Microsoft.Default
set_default CONTAINER_REGISTRY_NAME "${name_base}acr"
set_default STANDARD_AGENT_STORAGE_ACCOUNT_NAME "${name_base}st"
set_default STANDARD_AGENT_COSMOS_ACCOUNT_NAME "${name_base}cosmos"
set_default STANDARD_AGENT_SEARCH_NAME "${name_base}search"
set_default LOG_ANALYTICS_WORKSPACE_NAME "${name_base}-log"
set_default APPLICATION_INSIGHTS_NAME "${name_base}-appi"
set_default AZURE_MONITOR_PRIVATE_LINK_SCOPE_NAME "${name_base}-ampls"
set_default CONTAINER_APPS_ENVIRONMENT_NAME "${name_base}-cae"
set_default BACKEND_CONTAINER_APP_NAME "${name_base}-backend"
set_default FRONTEND_CONTAINER_APP_NAME "${name_base}-frontend"
set_default PRIVATE_BACKEND_MANAGED_IDENTITY_NAME "${name_base}-backend-mi"
set_default PRIVATE_FRONTEND_MANAGED_IDENTITY_NAME "${name_base}-frontend-mi"
set_default BACKEND_IMAGE_REPOSITORY order-resolution-private-backend
set_default FRONTEND_IMAGE_REPOSITORY order-resolution-private-frontend
set_default POSTGRES_SERVER_NAME "${name_base}pg"
set_default POSTGRES_DATABASE order_resolution
set_default POSTGRES_ADMIN_USERNAME pgadmin
set_default POSTGRES_RUNTIME_USERNAME order_resolution_runtime
set_default POSTGRES_SERVER_LOCATION "$location"
set_default PRIVATE_RUNNER_VM_NAME "${name_base}-runner"
set_default PRIVATE_RUNNER_WORKDIR /opt/order-resolution/source/agents/order-resolution/foundry-private
set_default PRIVATE_SOURCE_REPOSITORY_URL https://github.com/ppenumatsa1/langgraph-wf-monorepo.git
set_default BOOTSTRAP_RUNTIME_DATABASE_URL bootstrap-pending

set_sensitive_default POSTGRES_ADMIN_PASSWORD
set_sensitive_default PRIVATE_RUNNER_SSH_PUBLIC_KEY

runner_key="$(private_required_env_value PRIVATE_RUNNER_SSH_PUBLIC_KEY)"
[[ "$runner_key" =~ ^ssh-(ed25519|rsa|ecdsa)[[:space:]][A-Za-z0-9+/=]+([[:space:]][^[:space:]]+)?$ ]] ||
  private_die "PRIVATE_RUNNER_SSH_PUBLIC_KEY must be a single valid SSH public key"

echo "Prepared the selected private AZD environment for one-time bootstrap provisioning."
