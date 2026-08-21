#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

stage="${1:-}"
case "$stage" in
  deploy_backend|deploy_frontend|deploy_hosted) ;;
  *) private_die "runtime deployment stage mismatch" ;;
esac
for command in az jq python3; do
  private_require_command "$command"
done
private_require_target

python="$PRIVATE_ROOT_DIR/backend/.venv/bin/python"
[[ -x "$python" ]] || private_die "private runner requires backend/.venv for hosted deployment"

subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(private_azd_value AZURE_RESOURCE_GROUP)"
backend_name="$(private_required_env_value BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(private_required_env_value FRONTEND_CONTAINER_APP_NAME)"
backend_identity="$(private_required_env_value PRIVATE_BACKEND_MANAGED_IDENTITY_NAME)"
project_endpoint="$(private_required_env_value AZURE_AI_PROJECT_ENDPOINT)"
agent_name="$(private_required_env_value HOSTED_AGENT_NAME)"
model_name="$(private_required_env_value FOUNDRY_MODEL_DEPLOYMENT_NAME)"
runtime_connection="$(private_required_env_value FOUNDRY_RUNTIME_CONNECTION_NAME)"
runtime_database_url="$(private_required_env_value RUNTIME_DATABASE_URL)"
backend_image="$(private_required_env_value PRIVATE_BACKEND_IMAGE)"
frontend_image="$(private_required_env_value PRIVATE_FRONTEND_IMAGE)"
hosted_image="$(private_required_env_value PRIVATE_HOSTED_IMAGE)"

for image in "$backend_image" "$frontend_image" "$hosted_image"; do
  [[ "$image" =~ @sha256:[0-9a-f]{64}$ ]] ||
    private_die "private runtime deployments require immutable image digests"
done
[[ "$runtime_database_url" == postgresql+psycopg://* && "$runtime_database_url" == *"sslmode=require"* ]] ||
  private_die "private runtime database URL must use TLS"

backend_json="$(az containerapp show --subscription "$subscription_id" --resource-group "$resource_group" --name "$backend_name" --output json)"
frontend_json="$(az containerapp show --subscription "$subscription_id" --resource-group "$resource_group" --name "$frontend_name" --output json)"
jq -e '.properties.configuration.ingress.external == false' <<<"$backend_json" >/dev/null ||
  private_die "private backend ingress must remain internal"
jq -e '.properties.configuration.ingress.external == true' <<<"$frontend_json" >/dev/null ||
  private_die "private frontend must be the lane's only external ingress"

frontend_fqdn="$(jq -r '.properties.configuration.ingress.fqdn // empty' <<<"$frontend_json")"
backend_fqdn="$(jq -r '.properties.configuration.ingress.fqdn // empty' <<<"$backend_json")"
[[ -n "$frontend_fqdn" && -n "$backend_fqdn" ]] ||
  private_die "private Container App ingress FQDNs are required"
backend_client_id="$(az identity show --subscription "$subscription_id" --resource-group "$resource_group" --name "$backend_identity" --query clientId --output tsv)"
[[ -n "$backend_client_id" ]] || private_die "private backend managed identity is missing a client ID"

case "$stage" in
  deploy_backend)
    az containerapp secret set \
      --subscription "$subscription_id" \
      --resource-group "$resource_group" \
      --name "$backend_name" \
      --secrets "database-url=$runtime_database_url" \
      --output none
    az containerapp update \
      --subscription "$subscription_id" \
      --resource-group "$resource_group" \
      --name "$backend_name" \
      --image "$backend_image" \
      --set-env-vars \
        "APP_ENV=foundry-private-wrapper" \
        "STORE_PROVIDER=postgres" \
        "RUNTIME_TARGET=responses_wrapper" \
        "DATABASE_URL=secretref:database-url" \
        "RUNTIME_DATABASE_URL=secretref:database-url" \
        "DB_AUTH_MODE=password" \
        "DB_SCHEMA_MANAGED_EXTERNALLY=true" \
        "AZURE_CLIENT_ID=$backend_client_id" \
        "AZURE_TOKEN_CREDENTIALS=prod" \
        "AZURE_AI_PROJECT_ENDPOINT=$project_endpoint" \
        "FOUNDRY_PROJECTS_ENDPOINT=$project_endpoint" \
        "FOUNDRY_MODEL_DEPLOYMENT_NAME=$model_name" \
        "ENABLE_TELEMETRY=true" \
        "ENABLE_INSTRUMENTATION=true" \
        "OTEL_SERVICE_NAME=langgraph-order-resolution-private-backend" \
        "OTEL_SERVICE_NAMESPACE=langgraph-order-resolution-private" \
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false" \
        "OTEL_RECORD_CONTENT=false" \
        "FRONTEND_ORIGIN=https://$frontend_fqdn" \
      --output none
    jq -n --arg image "$backend_image" \
      '{component:"backend",image:$image,immutable_digest:true,public_access_opened:false}'
    ;;
  deploy_frontend)
    az containerapp update \
      --subscription "$subscription_id" \
      --resource-group "$resource_group" \
      --name "$frontend_name" \
      --image "$frontend_image" \
      --set-env-vars "API_BASE=" "NGINX_API_UPSTREAM=https://$backend_fqdn" \
      --output none
    jq -n --arg image "$frontend_image" \
      '{component:"frontend",image:$image,immutable_digest:true,public_access_opened:false}'
    ;;
  deploy_hosted)
    export FOUNDRY_PROJECT_ENDPOINT="$project_endpoint"
    export FOUNDRY_HOSTED_AGENT_NAME="$agent_name"
    export FOUNDRY_IMAGE="$hosted_image"
    export FOUNDRY_MODEL_DEPLOYMENT_NAME="$model_name"
    export FOUNDRY_RUNTIME_CONNECTION_NAME="$runtime_connection"
    hosted_output="$("$python" "$SCRIPT_DIR/deploy_hosted_agent.py")"
    hosted_version="$(sed -n 's/^HOSTED_AGENT_VERSION=//p' <<<"$hosted_output" | tail -n 1)"
    hosted_principal_id="$(sed -n 's/^HOSTED_AGENT_PRINCIPAL_ID=//p' <<<"$hosted_output" | tail -n 1)"
    [[ -n "$hosted_version" && -n "$hosted_principal_id" ]] ||
      private_die "private hosted deployment did not report an active version and identity"

    private_azd_set AGENT_ORDER_RESOLUTION_PRIVATE_HOSTED_NAME "$agent_name"
    private_azd_set AGENT_ORDER_RESOLUTION_PRIVATE_HOSTED_VERSION "$hosted_version"
    private_azd_set AGENT_ORDER_RESOLUTION_PRIVATE_HOSTED_IMAGE "$hosted_image"
    private_azd_set AGENT_ORDER_RESOLUTION_PRIVATE_HOSTED_PRINCIPAL_ID "$hosted_principal_id"
    jq -n \
      --arg image "$hosted_image" \
      --arg version "$hosted_version" \
      --arg principal_id "$hosted_principal_id" \
      '{component:"hosted_agent",image:$image,version:$version,principal_id:$principal_id,immutable_digest:true,public_access_opened:false}'
    ;;
esac
