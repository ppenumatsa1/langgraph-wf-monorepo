#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
PROFILE_PATH="${FOUNDRY_PACKAGE_VALIDATION_PROFILE:-$ROOT_DIR/deployment/profiles/foundry-public-package-validation.env}"
AZURE_CONFIG_PATH="$FOUNDRY_DIR/.azure/config.json"

source "$ROOT_DIR/deployment/profile.sh"

for command in azd sha256sum; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required binary: $command" >&2
    exit 1
  }
done

deployment_profile_load "$PROFILE_PATH"
deployment_profile_validate

env_name="${FOUNDRY_PACKAGE_ENV_NAME:-${DEPLOYMENT_PROFILE_VALUES[AZURE_ENV_NAME]}}"
subscription_id="${DEPLOYMENT_PROFILE_VALUES[AZURE_SUBSCRIPTION_ID]}"
resource_group="${DEPLOYMENT_PROFILE_VALUES[AZURE_RESOURCE_GROUP]}"
location="${DEPLOYMENT_PROFILE_VALUES[AZURE_LOCATION]}"
name_prefix="${DEPLOYMENT_PROFILE_VALUES[NAME_PREFIX]}"
resource_name_suffix="$(printf '%s' "${subscription_id}/${resource_group}" | sha256sum | cut -c1-8)"
resource_name_base="${name_prefix:0:12}${resource_name_suffix}"

foundry_account="${resource_name_base}ai"
foundry_project="order-resolution"
hosted_agent="order-resolution-hosted"
runtime_connection="orderresolutionruntimesecrets"
registry="${resource_name_base}acr"
postgres="${resource_name_base}pg"
environment="${resource_name_base}-cae"
backend="${resource_name_base}-backend"
frontend="${resource_name_base}-frontend"
backend_identity="${resource_name_base}-backend-mi"
frontend_identity="${resource_name_base}-frontend-mi"
app_insights="${resource_name_base}-ai"
log_analytics="${resource_name_base}-log"
evaluation_storage="${resource_name_base}eval"
project_endpoint="https://${foundry_account}.services.ai.azure.com/api/projects/${foundry_project}"
project_id="/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/${foundry_account}/projects/${foundry_project}"
responses_url="${project_endpoint}/agents/${hosted_agent}/endpoint/protocols/openai/responses?api-version=v1"
registry_endpoint="${registry}.azurecr.io"
postgres_fqdn="${postgres}.postgres.database.azure.com"
container_apps_environment_id="/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.App/managedEnvironments/${environment}"
backend_container_app_id="/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.App/containerApps/${backend}"
frontend_container_app_id="/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.App/containerApps/${frontend}"
appinsights_resource_id="/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.Insights/components/${app_insights}"
log_analytics_workspace_id="/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.OperationalInsights/workspaces/${log_analytics}"
config_existed=0
original_config=''

if [[ -f "$AZURE_CONFIG_PATH" ]]; then
  config_existed=1
  original_config="$(cat "$AZURE_CONFIG_PATH")"
fi

restore_config() {
  if [[ "$config_existed" -eq 1 ]]; then
    printf '%s' "$original_config" >"$AZURE_CONFIG_PATH"
  else
    rm -f "$AZURE_CONFIG_PATH"
  fi
}

trap restore_config EXIT

set_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env set -e "$env_name" "$1" "$2" --cwd "$FOUNDRY_DIR" --no-prompt >/dev/null
}

set_env AZURE_ENV_NAME "$env_name"
set_env AZURE_SUBSCRIPTION_ID "$subscription_id"
set_env AZURE_RESOURCE_GROUP "$resource_group"
set_env AZURE_LOCATION "$location"
set_env NAME_PREFIX "$name_prefix"
set_env INFRASTRUCTURE_MODE reuse
set_env FOUNDRY_LOCAL_VALIDATION_MODE package_validation
set_env RESOURCE_NAME_SUFFIX "$resource_name_suffix"
set_env FOUNDRY_ACCOUNT_NAME "$foundry_account"
set_env FOUNDRY_PROJECT_NAME "$foundry_project"
set_env FOUNDRY_CUSTOM_SUBDOMAIN_NAME "$foundry_account"
set_env AZURE_AI_PROJECT_ENDPOINT "$project_endpoint"
set_env AZURE_AI_PROJECT_ID "$project_id"
set_env FOUNDRY_PROJECT_ENDPOINT "$project_endpoint"
set_env FOUNDRY_PROJECTS_ENDPOINT "$project_endpoint"
set_env FOUNDRY_HOSTED_RESPONSES_URL "$responses_url"
set_env FOUNDRY_RESPONSES_ENDPOINT "$responses_url"
set_env HOSTED_AGENT_NAME "$hosted_agent"
set_env FOUNDRY_HOSTED_AGENT_NAME "$hosted_agent"
set_env FOUNDRY_RUNTIME_CONNECTION_NAME "$runtime_connection"
set_env FOUNDRY_MODEL_DEPLOYMENT_NAME order-resolution-gpt-4-1-mini
set_env FOUNDRY_MODEL_FORMAT OpenAI
set_env FOUNDRY_MODEL_NAME gpt-4.1-mini
set_env FOUNDRY_MODEL_VERSION 2025-04-14
set_env FOUNDRY_MODEL_SKU_NAME Standard
set_env FOUNDRY_MODEL_CAPACITY 1750
set_env FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME order-resolution-text-embedding-3-small
set_env FOUNDRY_EMBEDDINGS_MODEL_VERSION 1
set_env FOUNDRY_EMBEDDINGS_MODEL_CAPACITY 120
set_env FOUNDRY_EVAL_MODEL order-resolution-gpt-4-1-mini-evaluation
set_env FOUNDRY_EVALUATION_MODEL_CAPACITY 250
set_env FOUNDRY_RAI_POLICY_NAME Microsoft.Default
set_env CONTAINER_REGISTRY_NAME "$registry"
set_env AZURE_CONTAINER_REGISTRY_NAME "$registry"
set_env AZURE_CONTAINER_REGISTRY_ENDPOINT "$registry_endpoint"
set_env POSTGRES_SERVER_NAME "$postgres"
set_env AZURE_POSTGRES_SERVER_FQDN "$postgres_fqdn"
set_env POSTGRES_SERVER_LOCATION "$location"
set_env POSTGRES_DATABASE order_resolution
set_env POSTGRES_RUNTIME_USERNAME order_resolution_runtime
set_env POSTGRES_ADMIN_USERNAME pgadmin
set_env CONTAINER_APPS_ENVIRONMENT_NAME "$environment"
set_env AZURE_CONTAINER_APPS_ENVIRONMENT_ID "$container_apps_environment_id"
set_env BACKEND_CONTAINER_APP_ID "$backend_container_app_id"
set_env BACKEND_CONTAINER_APP_NAME "$backend"
set_env FRONTEND_CONTAINER_APP_ID "$frontend_container_app_id"
set_env FRONTEND_CONTAINER_APP_NAME "$frontend"
set_env PUBLIC_BACKEND_MANAGED_IDENTITY_NAME "$backend_identity"
set_env PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME "$frontend_identity"
set_env APPLICATION_INSIGHTS_NAME "$app_insights"
set_env APPLICATIONINSIGHTS_RESOURCE_ID "$appinsights_resource_id"
set_env LOG_ANALYTICS_WORKSPACE_NAME "$log_analytics"
set_env LOG_ANALYTICS_WORKSPACE_ID "$log_analytics_workspace_id"
set_env BACKEND_IMAGE_REPOSITORY order-resolution-public-backend
set_env FRONTEND_IMAGE_REPOSITORY order-resolution-public-frontend
set_env EVALUATION_STORAGE_ACCOUNT_NAME "$evaluation_storage"
set_env APP_ENV aca-public
set_env STORE_PROVIDER postgres
set_env RUNTIME_TARGET responses_wrapper
set_env DB_SCHEMA_MANAGED_EXTERNALLY true
set_env ENABLE_TELEMETRY true
set_env ENABLE_INSTRUMENTATION true
set_env OTEL_SERVICE_NAME langgraph-order-resolution-aca-backend
set_env OTEL_SERVICE_NAMESPACE langgraph-order-resolution
set_env OTEL_RECORD_CONTENT false
set_env FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT true
set_env FOUNDRY_HOSTED_OTEL_SERVICE_NAME langgraph-order-resolution-hosted
set_env FOUNDRY_OTEL_SERVICE_NAMESPACE langgraph-order-resolution
set_env OTEL_EXPORTER_OTLP_TRACES_ENDPOINT https://package-validation.invalid/v1/traces
set_env APPLICATIONINSIGHTS_CONNECTION_STRING "InstrumentationKey=00000000-0000-0000-0000-000000000000"
set_env APPINSIGHTS_CONNECTION_STRING "InstrumentationKey=00000000-0000-0000-0000-000000000000"
set_env API_BASE_URL "https://${backend}.package-validation.invalid"
set_env WEB_URL "https://${frontend}.package-validation.invalid"
set_env BOOTSTRAP_RUNTIME_DATABASE_URL package-validation-placeholder
set_env POSTGRES_ADMIN_PASSWORD package-validation-placeholder

trap - EXIT
restore_config

printf 'Prepared local azd package-validation environment %s without Azure hydration.\n' "$env_name"
