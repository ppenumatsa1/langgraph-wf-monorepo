#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

for command in az azd jq; do
  require_command "$command"
done
assert_target

subscription_id="$(required_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_azd_value AZURE_RESOURCE_GROUP)"
backend_name="$(required_azd_value BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(required_azd_value FRONTEND_CONTAINER_APP_NAME)"
backend_identity_name="$(required_azd_value PUBLIC_BACKEND_MANAGED_IDENTITY_NAME)"
project_endpoint="$(required_azd_value FOUNDRY_PROJECTS_ENDPOINT)"
model_deployment="$(required_azd_value FOUNDRY_MODEL_DEPLOYMENT_NAME)"
runtime_database_url="$(required_azd_value RUNTIME_DATABASE_URL)"
evidence_dir="$(release_evidence_dir)"
images_file="$evidence_dir/images.json"
[[ -f "$images_file" ]] || {
  echo "Image evidence is required; run build_images.sh first." >&2
  exit 1
}
backend_image="$(jq -er '.backend_image' "$images_file")"
frontend_image="$(jq -er '.frontend_image' "$images_file")"
[[ "$backend_image" =~ @sha256:[0-9a-f]{64}$ && "$frontend_image" =~ @sha256:[0-9a-f]{64}$ ]] || {
  echo "Application deployment accepts immutable image digests only." >&2
  exit 1
}

backend_client_id="$(az identity show --subscription "$subscription_id" \
  --resource-group "$resource_group" --name "$backend_identity_name" --query clientId -o tsv)"
backend_fqdn="$(az containerapp show --subscription "$subscription_id" \
  --resource-group "$resource_group" --name "$backend_name" \
  --query properties.configuration.ingress.fqdn -o tsv)"
frontend_fqdn="$(az containerapp show --subscription "$subscription_id" \
  --resource-group "$resource_group" --name "$frontend_name" \
  --query properties.configuration.ingress.fqdn -o tsv)"

az containerapp secret set --subscription "$subscription_id" --resource-group "$resource_group" \
  --name "$backend_name" --secrets "database-url=$runtime_database_url" --output none

az containerapp update --subscription "$subscription_id" --resource-group "$resource_group" \
  --name "$backend_name" --image "$backend_image" --min-replicas 1 --max-replicas 1 \
  --set-env-vars \
    "APP_ENV=azure-hosted" \
    "STORE_PROVIDER=postgres" \
    "RUNTIME_TARGET=direct_langgraph" \
    "DATABASE_URL=secretref:database-url" \
    "RUNTIME_DATABASE_URL=secretref:database-url" \
    "DB_SCHEMA_MANAGED_EXTERNALLY=true" \
    "AZURE_CLIENT_ID=${backend_client_id}" \
    "AZURE_TOKEN_CREDENTIALS=prod" \
    "AZURE_AI_PROJECT_ENDPOINT=${project_endpoint}" \
    "FOUNDRY_PROJECTS_ENDPOINT=${project_endpoint}" \
    "FOUNDRY_MODEL_DEPLOYMENT_NAME=${model_deployment}" \
    "ENABLE_TELEMETRY=true" \
    "ENABLE_INSTRUMENTATION=true" \
    "OTEL_SERVICE_NAME=langgraph-order-resolution-azure-backend" \
    "OTEL_SERVICE_NAMESPACE=langgraph-order-resolution" \
    "OTEL_RECORD_CONTENT=false" \
    "FRONTEND_ORIGIN=https://${frontend_fqdn}" \
  --output none &
backend_pid=$!

az containerapp update --subscription "$subscription_id" --resource-group "$resource_group" \
  --name "$frontend_name" --image "$frontend_image" --min-replicas 1 \
  --set-env-vars "API_BASE=" "NGINX_API_UPSTREAM=https://${backend_fqdn}" \
  --output none &
frontend_pid=$!

wait "$backend_pid"
wait "$frontend_pid"

jq -n \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg backend_image "$backend_image" \
  --arg frontend_image "$frontend_image" \
  '{status:"passed",generated_at:$generated_at,backend_image:$backend_image,frontend_image:$frontend_image}' \
  >"$evidence_dir/deployment.json"
