#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

for command in az azd curl sha256sum; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required binary: $command" >&2
    exit 1
  }
done

get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
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
    echo "Missing selected AZD environment value: $name" >&2
    exit 1
  fi
  printf '%s' "$value"
}

set_if_missing() {
  local name="$1"
  local value="$2"
  if [[ -z "$(get_env "$name")" && -n "$value" ]]; then
    set_env "$name" "$value"
  fi
}

if [[ "$(get_env INFRASTRUCTURE_MODE)" == "bootstrap" && "${FOUNDRY_BOOTSTRAP_HYDRATE:-0}" != "1" ]]; then
  echo "Bootstrap parameters are selected; outputs will be hydrated after provisioning."
  exit 0
fi

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
target_location="$(required_env AZURE_LOCATION)"
name_prefix="$(required_env NAME_PREFIX)"
normalized_prefix="$(printf '%s' "$name_prefix" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')"
resource_name_suffix="$(printf '%s' "${subscription_id}/${resource_group}" | sha256sum | cut -c1-8)"
resource_name_base="${normalized_prefix:0:12}${resource_name_suffix}"
set_if_missing FOUNDRY_ACCOUNT_NAME "${resource_name_base}ai"
set_if_missing FOUNDRY_PROJECT_NAME order-resolution
set_if_missing HOSTED_AGENT_NAME order-resolution-hosted
set_if_missing FOUNDRY_RUNTIME_CONNECTION_NAME orderresolutionruntimesecrets
set_if_missing FOUNDRY_MODEL_DEPLOYMENT_NAME order-resolution-gpt-4-1-mini
set_if_missing FOUNDRY_MODEL_FORMAT OpenAI
set_if_missing FOUNDRY_MODEL_NAME gpt-4.1-mini
set_if_missing FOUNDRY_MODEL_VERSION 2025-04-14
set_if_missing FOUNDRY_MODEL_SKU_NAME Standard
set_if_missing FOUNDRY_MODEL_CAPACITY 1750
set_if_missing FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME order-resolution-text-embedding-3-small
set_if_missing FOUNDRY_EMBEDDINGS_MODEL_VERSION 1
set_if_missing FOUNDRY_EMBEDDINGS_MODEL_CAPACITY 120
set_if_missing FOUNDRY_EVAL_MODEL order-resolution-gpt-4-1-mini-evaluation
set_if_missing FOUNDRY_EVALUATION_MODEL_CAPACITY 250
set_if_missing FOUNDRY_RAI_POLICY_NAME Microsoft.Default
set_if_missing CONTAINER_REGISTRY_NAME "${resource_name_base}acr"
set_if_missing POSTGRES_SERVER_NAME "${resource_name_base}pg"
set_if_missing POSTGRES_DATABASE order_resolution
set_if_missing POSTGRES_RUNTIME_USERNAME order_resolution_runtime
set_if_missing POSTGRES_ADMIN_USERNAME pgadmin
set_if_missing CONTAINER_APPS_ENVIRONMENT_NAME "${resource_name_base}-cae"
set_if_missing BACKEND_CONTAINER_APP_NAME "${resource_name_base}-backend"
set_if_missing FRONTEND_CONTAINER_APP_NAME "${resource_name_base}-frontend"
set_if_missing PUBLIC_BACKEND_MANAGED_IDENTITY_NAME "${resource_name_base}-backend-mi"
set_if_missing PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME "${resource_name_base}-frontend-mi"
set_if_missing APPLICATION_INSIGHTS_NAME "${resource_name_base}-ai"
set_if_missing LOG_ANALYTICS_WORKSPACE_NAME "${resource_name_base}-log"
set_if_missing BACKEND_IMAGE_REPOSITORY order-resolution-public-backend
set_if_missing FRONTEND_IMAGE_REPOSITORY order-resolution-public-frontend
set_if_missing EVALUATION_STORAGE_ACCOUNT_NAME "${resource_name_base}eval"
set_if_missing BOOTSTRAP_RUNTIME_DATABASE_URL reuse-placeholder
set_if_missing POSTGRES_ADMIN_PASSWORD reuse-placeholder
foundry_account="$(required_env FOUNDRY_ACCOUNT_NAME)"
foundry_project="$(required_env FOUNDRY_PROJECT_NAME)"
registry="$(required_env CONTAINER_REGISTRY_NAME)"
postgres="$(required_env POSTGRES_SERVER_NAME)"
environment="$(required_env CONTAINER_APPS_ENVIRONMENT_NAME)"
backend="$(required_env BACKEND_CONTAINER_APP_NAME)"
frontend="$(required_env FRONTEND_CONTAINER_APP_NAME)"
backend_identity="$(required_env PUBLIC_BACKEND_MANAGED_IDENTITY_NAME)"
frontend_identity="$(required_env PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME)"
app_insights="$(required_env APPLICATION_INSIGHTS_NAME)"
log_analytics="$(required_env LOG_ANALYTICS_WORKSPACE_NAME)"
hosted_agent="$(required_env HOSTED_AGENT_NAME)"
runtime_connection="$(required_env FOUNDRY_RUNTIME_CONNECTION_NAME)"

az account set --subscription "$subscription_id"
azd auth login --check-status >/dev/null
location="$(az group show --name "$resource_group" --query location -o tsv)"
if [[ "${location,,}" != "${target_location,,}" ]]; then
  echo "Selected AZD location does not match the resource group." >&2
  exit 1
fi
if [[ "${POSTGRES_REBUILD:-0}" == "1" ]]; then
  postgres_location="$(required_env POSTGRES_SERVER_LOCATION)"
else
  postgres_location="$(az postgres flexible-server show --subscription "$subscription_id" --resource-group "$resource_group" --name "$postgres" --query location -o tsv)"
fi

operator_ip="$(get_env POSTGRES_OPERATOR_IP)"
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

set_env INFRASTRUCTURE_MODE reuse
set_env AZURE_SUBSCRIPTION_ID "$subscription_id"
set_env AZURE_RESOURCE_GROUP "$resource_group"
set_env AZURE_LOCATION "$location"
set_env FOUNDRY_ACCOUNT_NAME "$foundry_account"
set_env FOUNDRY_PROJECT_NAME "$foundry_project"
set_env FOUNDRY_CUSTOM_SUBDOMAIN_NAME "$foundry_account"
set_env AZURE_AI_PROJECT_ENDPOINT "$project_endpoint"
set_env AZURE_AI_PROJECT_ID "$project_id"
set_env FOUNDRY_PROJECT_ENDPOINT "$project_endpoint"
set_env FOUNDRY_PROJECTS_ENDPOINT "$project_endpoint"
set_env FOUNDRY_HOSTED_RESPONSES_URL "$responses_url"
set_env FOUNDRY_RESPONSES_ENDPOINT "$responses_url"
set_env FOUNDRY_MODEL_DEPLOYMENT_NAME "$(required_env FOUNDRY_MODEL_DEPLOYMENT_NAME)"
set_env FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME "$(required_env FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME)"
set_env FOUNDRY_EVAL_MODEL "$(required_env FOUNDRY_EVAL_MODEL)"
set_env HOSTED_AGENT_NAME "$hosted_agent"
set_env FOUNDRY_RUNTIME_CONNECTION_NAME "$runtime_connection"
set_env CONTAINER_REGISTRY_NAME "$registry"
set_env AZURE_CONTAINER_REGISTRY_NAME "$registry"
set_env AZURE_CONTAINER_REGISTRY_ENDPOINT "$registry_endpoint"
set_env LOG_ANALYTICS_WORKSPACE_ID "$log_analytics_workspace_id"
set_env AZURE_POSTGRES_SERVER_FQDN "$postgres_fqdn"
set_env POSTGRES_SERVER_NAME "$postgres"
set_env POSTGRES_SERVER_LOCATION "$postgres_location"
set_env POSTGRES_OPERATOR_IP "$operator_ip"
set_env POSTGRES_DATABASE "$(required_env POSTGRES_DATABASE)"
set_env DB_AUTH_MODE password
set_env AZURE_CONTAINER_APPS_ENVIRONMENT_ID "$container_apps_environment_id"
set_env CONTAINER_APPS_ENVIRONMENT_NAME "$environment"
set_env BACKEND_CONTAINER_APP_ID "$backend_container_app_id"
set_env BACKEND_CONTAINER_APP_NAME "$backend"
set_env FRONTEND_CONTAINER_APP_ID "$frontend_container_app_id"
set_env FRONTEND_CONTAINER_APP_NAME "$frontend"
set_env PUBLIC_BACKEND_MANAGED_IDENTITY_NAME "$backend_identity"
set_env PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME "$frontend_identity"
set_env BACKEND_IMAGE_REPOSITORY "$(required_env BACKEND_IMAGE_REPOSITORY)"
set_env FRONTEND_IMAGE_REPOSITORY "$(required_env FRONTEND_IMAGE_REPOSITORY)"
set_env API_BASE_URL "https://${backend_fqdn}"
set_env WEB_URL "https://${frontend_fqdn}"
set_env AZURE_OPENAI_ENDPOINT "$foundry_endpoint"
set_env APPLICATIONINSIGHTS_CONNECTION_STRING "$appinsights_connection_string"
set_env APPINSIGHTS_CONNECTION_STRING "$appinsights_connection_string"
set_env APPLICATIONINSIGHTS_RESOURCE_ID "$appinsights_resource_id"

printf 'Hydrated secret-free target outputs for %s/%s (%s, %s, %s, %s, %s).\n' \
  "$subscription_id" "$resource_group" "$environment" "$backend" "$frontend" "$app_insights" "$log_analytics"
