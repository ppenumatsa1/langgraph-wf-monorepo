#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
BACKEND_DOCKERFILE="$ROOT_DIR/infra/foundry-hosted/runtime/Dockerfile.backend-release"

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

for command in az azd git jq sha256sum; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required binary: $command" >&2
    exit 1
  }
done

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"
[[ -f "$BACKEND_DOCKERFILE" ]] || {
  echo "Missing backend release Dockerfile: $BACKEND_DOCKERFILE" >&2
  exit 1
}
subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
registry_name="$(required_env AZURE_CONTAINER_REGISTRY_NAME)"
registry_endpoint="$(required_env AZURE_CONTAINER_REGISTRY_ENDPOINT)"
backend_name="$(required_env BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(required_env FRONTEND_CONTAINER_APP_NAME)"
backend_identity_name="$(required_env PUBLIC_BACKEND_MANAGED_IDENTITY_NAME)"
image_repository="$(required_env BACKEND_IMAGE_REPOSITORY)"
runtime_database_url="$(required_env RUNTIME_DATABASE_URL)"
project_endpoint="$(required_env AZURE_AI_PROJECT_ENDPOINT)"
responses_endpoint="$(required_env FOUNDRY_RESPONSES_ENDPOINT)"
model_deployment="$(required_env FOUNDRY_MODEL_DEPLOYMENT_NAME)"
embeddings_deployment="$(required_env FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME)"

[[ "$subscription_id" == "7df95e88-701c-4693-af77-3159f83b558d" ]] &&
  [[ "$resource_group" == "rg-langgraph-ora-foundry-public" ]] || {
  echo "Backend deployment requires the canonical public target." >&2
  exit 1
}

az account set --subscription "$subscription_id"
frontend_fqdn="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$frontend_name" \
    --query properties.configuration.ingress.fqdn \
    --output tsv
)"
backend_identity_client_id="$(
  az identity show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_identity_name" \
    --query clientId \
    --output tsv
)"
source_revision="$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD 2>/dev/null || true)"
[[ -n "$source_revision" ]] || source_revision=uncommitted
image_tag="${source_revision}-$(date -u +%Y%m%d%H%M%S)"
tagged_image="${registry_endpoint}/${image_repository}:${image_tag}"

az acr build \
  --subscription "$subscription_id" \
  --registry "$registry_name" \
  --image "${image_repository}:${image_tag}" \
  --file "$BACKEND_DOCKERFILE" \
  "$ROOT_DIR"
image_digest="$(
  az acr repository show \
    --subscription "$subscription_id" \
    --name "$registry_name" \
    --image "${image_repository}:${image_tag}" \
    --query digest \
    --output tsv
)"
[[ "$image_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || {
  echo "Backend image digest was not returned by ACR." >&2
  exit 1
}
image="${registry_endpoint}/${image_repository}@${image_digest}"
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
  --image "$image" \
  --set-env-vars \
    "APP_ENV=aca-public" \
    "STORE_PROVIDER=postgres" \
    "RUNTIME_TARGET=responses_wrapper" \
    "DATABASE_URL=secretref:database-url" \
    "RUNTIME_DATABASE_URL=secretref:database-url" \
    "DB_AUTH_MODE=password" \
    "DB_SCHEMA_MANAGED_EXTERNALLY=true" \
    "AZURE_CLIENT_ID=${backend_identity_client_id}" \
    "AZURE_TOKEN_CREDENTIALS=prod" \
    "AZURE_AI_PROJECT_ENDPOINT=${project_endpoint}" \
    "FOUNDRY_PROJECTS_ENDPOINT=${project_endpoint}" \
    "FOUNDRY_RESPONSES_ENDPOINT=${responses_endpoint}" \
    "FOUNDRY_MODEL_DEPLOYMENT_NAME=${model_deployment}" \
    "FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME=${embeddings_deployment}" \
    "ENABLE_TELEMETRY=true" \
    "ENABLE_INSTRUMENTATION=true" \
    "OTEL_SERVICE_NAME=langgraph-order-resolution-aca-backend" \
    "OTEL_SERVICE_NAMESPACE=langgraph-order-resolution" \
    "OTEL_RECORD_CONTENT=false" \
    "FRONTEND_ORIGIN=https://${frontend_fqdn}" \
  --output none
az containerapp ingress update \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --name "$backend_name" \
  --target-port 8000 \
  --transport http \
  --output none

release_id="${FOUNDRY_RELEASE_ID:-manual-backend-deploy}"
release_started_at="${FOUNDRY_RELEASE_STARTED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
revision_name="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --query properties.latestRevisionName \
    --output tsv
)"
database_url_sha256="$(printf '%s' "$runtime_database_url" | sha256sum | cut -d' ' -f1)"
metadata_file="${PUBLIC_BACKEND_DEPLOYMENT_METADATA_FILE:-$ROOT_DIR/backend/.foundry/results/backend-deployment.json}"
mkdir -p "$(dirname "$metadata_file")"
jq -n \
  --arg release_id "$release_id" \
  --arg release_started_at "$release_started_at" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg container_app "$backend_name" \
  --arg revision "$revision_name" \
  --arg tagged_image "$tagged_image" \
  --arg image "$image" \
  --arg database_url_sha256 "$database_url_sha256" \
  '{
    schema_version: 1,
    evidence_type: "component_deployment",
    component: "backend",
    status: "deployed",
    release_id: $release_id,
    release_started_at: $release_started_at,
    generated_at: $generated_at,
    container_app: $container_app,
    revision: $revision,
    tagged_image: $tagged_image,
    image: $image,
    database_url_sha256: $database_url_sha256,
    schema_managed_externally: true
  }' >"$metadata_file"

echo "PUBLIC_BACKEND_IMAGE=$image"
echo "PUBLIC_BACKEND_REVISION=$revision_name"
