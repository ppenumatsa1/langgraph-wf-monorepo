#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

require_bin az
require_bin azd
require_bin curl

azd_environment="${FOUNDRY_AZD_ENV_NAME:-${AZD_ENV_NAME:-}}"

if [[ -n "$azd_environment" ]]; then
  (
    cd "$FOUNDRY_DIR"
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env select "$azd_environment" --no-prompt
  )
fi

get_env_value() {
  local value
  if ! value="$(
    cd "$FOUNDRY_DIR"
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$1" --no-prompt 2>/dev/null
  )"; then
    return 0
  fi
  printf '%s' "$value"
}

set_if_missing() {
  local key="$1"
  local value="$2"
  local existing
  existing="$(get_env_value "$key")"
  if [[ -z "$existing" && -n "$value" ]]; then
    (
      cd "$FOUNDRY_DIR"
      AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set "$key" "$value" --no-prompt >/dev/null
    )
  fi
}

required_env_value() {
  local key="$1"
  local value
  value="$(get_env_value "$key")"
  if [[ -z "$value" ]]; then
    echo "Missing selected AZD environment value: $key" >&2
    exit 1
  fi
  printf '%s' "$value"
}

if [[ "$(get_env_value INFRASTRUCTURE_MODE)" == "bootstrap" && "${FOUNDRY_BOOTSTRAP_HYDRATE:-0}" != "1" ]]; then
  echo "Bootstrap parameters are selected; infrastructure outputs will be hydrated after provisioning."
  exit 0
fi

subscription_id="$(required_env_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env_value AZURE_RESOURCE_GROUP)"
target_location="$(required_env_value AZURE_LOCATION)"
name_prefix="$(required_env_value NAME_PREFIX)"
normalized_prefix="$(printf '%s' "$name_prefix" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')"
resource_name_suffix="$(printf '%s' "${subscription_id}/${resource_group}" | sha256sum | cut -c1-8)"
resource_name_base="${normalized_prefix:0:12}${resource_name_suffix}"
set_if_missing FOUNDRY_ACCOUNT_NAME "${resource_name_base}ai"
set_if_missing FOUNDRY_PROJECT_NAME underwriting
set_if_missing HOSTED_AGENT_NAME underwriting-hosted
set_if_missing FOUNDRY_RUNTIME_CONNECTION_NAME underwritingruntimesecrets
set_if_missing FOUNDRY_MODEL_DEPLOYMENT_NAME underwriting-gpt-4-1-mini
set_if_missing FOUNDRY_MODEL_FORMAT OpenAI
set_if_missing FOUNDRY_MODEL_NAME gpt-4.1-mini
set_if_missing FOUNDRY_MODEL_VERSION 2025-04-14
set_if_missing FOUNDRY_MODEL_SKU_NAME DataZoneStandard
set_if_missing FOUNDRY_MODEL_CAPACITY 1500
set_if_missing FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME underwriting-text-embedding-3-small
set_if_missing FOUNDRY_EMBEDDINGS_MODEL_VERSION 1
set_if_missing FOUNDRY_EMBEDDINGS_MODEL_CAPACITY 120
set_if_missing FOUNDRY_EVAL_MODEL underwriting-gpt-4-1-mini-evaluation
set_if_missing FOUNDRY_EVALUATION_MODEL_CAPACITY 250
set_if_missing FOUNDRY_RAI_POLICY_NAME Microsoft.Default
set_if_missing CONTAINER_REGISTRY_NAME "${resource_name_base}acr"
set_if_missing POSTGRES_SERVER_NAME "${resource_name_base}pg"
set_if_missing POSTGRES_DATABASE underwriting
set_if_missing POSTGRES_RUNTIME_USERNAME underwriting_runtime
set_if_missing POSTGRES_ADMIN_USERNAME pgadmin
set_if_missing CONTAINER_APPS_ENVIRONMENT_NAME "${resource_name_base}-cae"
set_if_missing BACKEND_CONTAINER_APP_NAME "${resource_name_base}-backend"
set_if_missing FRONTEND_CONTAINER_APP_NAME "${resource_name_base}-frontend"
set_if_missing PUBLIC_BACKEND_MANAGED_IDENTITY_NAME "${resource_name_base}-backend-mi"
set_if_missing PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME "${resource_name_base}-frontend-mi"
set_if_missing APPLICATION_INSIGHTS_NAME "${resource_name_base}-ai"
set_if_missing LOG_ANALYTICS_WORKSPACE_NAME "${resource_name_base}-log"
set_if_missing BACKEND_IMAGE_REPOSITORY underwriting-public-backend
set_if_missing FRONTEND_IMAGE_REPOSITORY underwriting-public-frontend
set_if_missing EVALUATION_STORAGE_ACCOUNT_NAME "${resource_name_base}eval"
set_if_missing BOOTSTRAP_RUNTIME_DATABASE_URL reuse-placeholder
set_if_missing POSTGRES_ADMIN_PASSWORD reuse-placeholder
foundry_account="$(required_env_value FOUNDRY_ACCOUNT_NAME)"
foundry_project="$(required_env_value FOUNDRY_PROJECT_NAME)"
registry="$(required_env_value CONTAINER_REGISTRY_NAME)"
postgres="$(required_env_value POSTGRES_SERVER_NAME)"
environment="$(required_env_value CONTAINER_APPS_ENVIRONMENT_NAME)"
backend="$(required_env_value BACKEND_CONTAINER_APP_NAME)"
backend_identity="$(required_env_value PUBLIC_BACKEND_MANAGED_IDENTITY_NAME)"
frontend="$(required_env_value FRONTEND_CONTAINER_APP_NAME)"
frontend_identity="$(required_env_value PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME)"
app_insights="$(required_env_value APPLICATION_INSIGHTS_NAME)"
log_analytics="$(required_env_value LOG_ANALYTICS_WORKSPACE_NAME)"
hosted_agent="$(required_env_value HOSTED_AGENT_NAME)"

az account set --subscription "$subscription_id" >/dev/null
azd auth login --check-status >/dev/null
location="$(az group show --name "$resource_group" --query location -o tsv)"
if [[ "${location,,}" != "${target_location,,}" ]]; then
  echo "Selected AZD location does not match the resource group." >&2
  exit 1
fi
if [[ "${POSTGRES_REBUILD:-0}" == "1" ]]; then
  postgres_location="$(required_env_value POSTGRES_SERVER_LOCATION)"
else
  postgres_location="$(
    az postgres flexible-server show \
      --subscription "$subscription_id" \
      --resource-group "$resource_group" \
      --name "$postgres" \
      --query location \
      --output tsv
  )"
fi

operator_ip="$(get_env_value POSTGRES_OPERATOR_IP)"
if [[ -z "$operator_ip" ]]; then
  operator_ip="$(curl --fail --silent --show-error --max-time 10 https://api.ipify.org)"
fi
if [[ ! "$operator_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
  echo "POSTGRES_OPERATOR_IP must be a public IPv4 address." >&2
  exit 1
fi

registry_endpoint="$(az acr show --resource-group "$resource_group" --name "$registry" --query loginServer -o tsv)"
foundry_endpoint="$(az cognitiveservices account show --resource-group "$resource_group" --name "$foundry_account" --query properties.endpoint -o tsv)"
appinsights_connection_string="$(az monitor app-insights component show --resource-group "$resource_group" --app "$app_insights" --query connectionString -o tsv)"
appinsights_resource_id="$(az monitor app-insights component show --resource-group "$resource_group" --app "$app_insights" --query id -o tsv)"
log_analytics_workspace_id="$(az monitor log-analytics workspace show --resource-group "$resource_group" --workspace-name "$log_analytics" --query id -o tsv)"
postgres_fqdn="$(az postgres flexible-server show --subscription "$subscription_id" --resource-group "$resource_group" --name "$postgres" --query fullyQualifiedDomainName -o tsv)"
container_apps_environment_id="$(az containerapp env show --resource-group "$resource_group" --name "$environment" --query id -o tsv)"
backend_container_app_id="$(az containerapp show --resource-group "$resource_group" --name "$backend" --query id -o tsv)"
backend_fqdn="$(az containerapp show --resource-group "$resource_group" --name "$backend" --query properties.configuration.ingress.fqdn -o tsv)"
frontend_container_app_id="$(az containerapp show --resource-group "$resource_group" --name "$frontend" --query id -o tsv)"
frontend_fqdn="$(az containerapp show --resource-group "$resource_group" --name "$frontend" --query properties.configuration.ingress.fqdn -o tsv)"
project_endpoint="https://${foundry_account}.services.ai.azure.com/api/projects/${foundry_project}"
project_id="/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/${foundry_account}/projects/${foundry_project}"
responses_url="${project_endpoint}/agents/${hosted_agent}/endpoint/protocols/openai/responses?api-version=v1"

(
  cd "$FOUNDRY_DIR"

  set_value() {
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set "$1" "$2" --no-prompt >/dev/null
  }

  set_value INFRASTRUCTURE_MODE reuse
  set_value AZURE_SUBSCRIPTION_ID "$subscription_id"
  set_value AZURE_RESOURCE_GROUP "$resource_group"
  set_value AZURE_LOCATION "$location"
  set_value NAME_PREFIX "$normalized_prefix"
  set_value RESOURCE_NAME_SUFFIX "$resource_name_suffix"
  set_value FOUNDRY_ACCOUNT_NAME "$foundry_account"
  set_value FOUNDRY_PROJECT_NAME "$foundry_project"
  set_value FOUNDRY_CUSTOM_SUBDOMAIN_NAME "$foundry_account"
  set_value AZURE_AI_PROJECT_ENDPOINT "$project_endpoint"
  set_value AZURE_AI_PROJECT_ID "$project_id"
  set_value FOUNDRY_PROJECT_ENDPOINT "$project_endpoint"
  set_value FOUNDRY_PROJECTS_ENDPOINT "$project_endpoint"
  set_value FOUNDRY_HOSTED_RESPONSES_URL "$responses_url"
  set_value FOUNDRY_RESPONSES_ENDPOINT "$responses_url"
  set_value HOSTED_AGENT_NAME "$hosted_agent"
  set_value FOUNDRY_HOSTED_AGENT_NAME "$hosted_agent"
  set_value FOUNDRY_RUNTIME_CONNECTION_NAME "$(required_env_value FOUNDRY_RUNTIME_CONNECTION_NAME)"
  set_value FOUNDRY_MODEL_DEPLOYMENT_NAME "$(required_env_value FOUNDRY_MODEL_DEPLOYMENT_NAME)"
  set_value FOUNDRY_MODEL_FORMAT "$(required_env_value FOUNDRY_MODEL_FORMAT)"
  set_value FOUNDRY_MODEL_NAME "$(required_env_value FOUNDRY_MODEL_NAME)"
  set_value FOUNDRY_MODEL_VERSION "$(required_env_value FOUNDRY_MODEL_VERSION)"
  set_value FOUNDRY_MODEL_SKU_NAME "$(required_env_value FOUNDRY_MODEL_SKU_NAME)"
  set_value FOUNDRY_MODEL_CAPACITY "$(required_env_value FOUNDRY_MODEL_CAPACITY)"
  set_value FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME "$(required_env_value FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME)"
  set_value FOUNDRY_EMBEDDINGS_MODEL_VERSION "$(required_env_value FOUNDRY_EMBEDDINGS_MODEL_VERSION)"
  set_value FOUNDRY_EMBEDDINGS_MODEL_CAPACITY "$(required_env_value FOUNDRY_EMBEDDINGS_MODEL_CAPACITY)"
  set_value FOUNDRY_EVAL_MODEL "$(required_env_value FOUNDRY_EVAL_MODEL)"
  set_value FOUNDRY_EVALUATION_MODEL_CAPACITY "$(required_env_value FOUNDRY_EVALUATION_MODEL_CAPACITY)"
  set_value FOUNDRY_RAI_POLICY_NAME "$(required_env_value FOUNDRY_RAI_POLICY_NAME)"
  set_value CONTAINER_REGISTRY_NAME "$registry"
  set_value AZURE_CONTAINER_REGISTRY_NAME "$registry"
  set_value AZURE_CONTAINER_REGISTRY_ENDPOINT "$registry_endpoint"
  set_value LOG_ANALYTICS_WORKSPACE_ID "$log_analytics_workspace_id"
  set_value AZURE_POSTGRES_SERVER_FQDN "$postgres_fqdn"
  set_value POSTGRES_SERVER_NAME "$postgres"
  set_value POSTGRES_SERVER_LOCATION "$postgres_location"
  set_value POSTGRES_OPERATOR_IP "$operator_ip"
  set_value POSTGRES_DATABASE "$(required_env_value POSTGRES_DATABASE)"
  set_value POSTGRES_RUNTIME_USERNAME "$(required_env_value POSTGRES_RUNTIME_USERNAME)"
  set_value POSTGRES_ADMIN_USERNAME "$(required_env_value POSTGRES_ADMIN_USERNAME)"
  set_value DB_AUTH_MODE password
  set_value DB_SCHEMA_MANAGED_EXTERNALLY true
  set_value AZURE_CONTAINER_APPS_ENVIRONMENT_ID "$container_apps_environment_id"
  set_value CONTAINER_APPS_ENVIRONMENT_NAME "$environment"
  set_value BACKEND_CONTAINER_APP_ID "$backend_container_app_id"
  set_value BACKEND_CONTAINER_APP_NAME "$backend"
  set_value FRONTEND_CONTAINER_APP_ID "$frontend_container_app_id"
  set_value FRONTEND_CONTAINER_APP_NAME "$frontend"
  set_value PUBLIC_BACKEND_MANAGED_IDENTITY_NAME "$backend_identity"
  set_value PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME "$frontend_identity"
  set_value BACKEND_IMAGE_REPOSITORY "$(required_env_value BACKEND_IMAGE_REPOSITORY)"
  set_value FRONTEND_IMAGE_REPOSITORY "$(required_env_value FRONTEND_IMAGE_REPOSITORY)"
  set_value API_BASE_URL "https://${backend_fqdn}"
  set_value WEB_URL "https://${frontend_fqdn}"
  set_value AZURE_OPENAI_ENDPOINT "$foundry_endpoint"
  set_value APPLICATIONINSIGHTS_CONNECTION_STRING "$appinsights_connection_string"
  set_value APPINSIGHTS_CONNECTION_STRING "$appinsights_connection_string"
  set_value APPLICATIONINSIGHTS_RESOURCE_ID "$appinsights_resource_id"
)

printf 'Hydrated secret-free target outputs for %s/%s (%s, %s, %s, %s, %s).\n' \
  "$subscription_id" "$resource_group" "$environment" "$backend" "$frontend" "$app_insights" "$log_analytics"
