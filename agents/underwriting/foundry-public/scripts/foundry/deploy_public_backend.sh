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

get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
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

require_bin az
require_bin azd
require_bin curl
require_bin git

if [[ -z "${PUBLIC_BACKEND_PREBUILT_IMAGE:-}" ]]; then
  "$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"
fi

resource_group="$(required_env AZURE_RESOURCE_GROUP)"
subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
location="$(required_env AZURE_LOCATION)"
registry_name="$(required_env AZURE_CONTAINER_REGISTRY_NAME)"
registry_endpoint="$(required_env AZURE_CONTAINER_REGISTRY_ENDPOINT)"
backend_name="$(required_env BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(required_env FRONTEND_CONTAINER_APP_NAME)"
backend_identity_name="$(required_env PUBLIC_BACKEND_MANAGED_IDENTITY_NAME)"
image_repository="$(required_env BACKEND_IMAGE_REPOSITORY)"
runtime_database_url="$(required_env RUNTIME_DATABASE_URL)"
project_endpoint="$(required_env AZURE_AI_PROJECT_ENDPOINT)"
hosted_agent_name="$(required_env AGENT_UNDERWRITING_HOSTED_NAME)"
hosted_agent_version="$(required_env AGENT_UNDERWRITING_HOSTED_VERSION)"
responses_endpoint="$(required_env AGENT_UNDERWRITING_HOSTED_RESPONSES_ENDPOINT)"
database_url="$(get_env DATABASE_URL)"
if [[ -n "$database_url" && "$database_url" != "$runtime_database_url" ]]; then
  echo "DATABASE_URL and RUNTIME_DATABASE_URL must match before backend deployment." >&2
  exit 1
fi

az account set --subscription "$subscription_id" >/dev/null
[[ "$subscription_id" == "7df95e88-701c-4693-af77-3159f83b558d" &&
  "$resource_group" == "rg-langgraph-uw-foundry-public" &&
  "${location,,}" == "eastus2" ]] || {
  echo "Backend deployment requires the canonical Underwriting public target." >&2
  exit 1
}
backend_external="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --query 'properties.configuration.ingress.external' \
    --output tsv
)"
backend_external="${backend_external,,}"
if [[ "$backend_external" != "false" ]]; then
  echo "Backend ingress must already be internal. Use the one-time foundry-backend-internalize command for migration." >&2
  exit 1
fi
frontend_fqdn="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$frontend_name" \
    --query 'properties.configuration.ingress.fqdn' \
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
[[ -n "$backend_identity_client_id" ]] || {
  echo "Backend managed identity did not return a client ID." >&2
  exit 1
}
image="${PUBLIC_BACKEND_PREBUILT_IMAGE:-}"
if [[ -z "$image" ]]; then
  image_tag="$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)"
  az acr build \
    --subscription "$subscription_id" \
    --registry "$registry_name" \
    --image "${image_repository}:${image_tag}" \
    --file "$ROOT_DIR/backend/Dockerfile" \
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
elif [[ "$image" != *@sha256:* ]]; then
  echo "PUBLIC_BACKEND_PREBUILT_IMAGE must be pinned by digest." >&2
  exit 1
fi

current_image="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --query 'properties.template.containers[0].image' \
    --output tsv
)"
current_hosted_version="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --query "properties.template.containers[0].env[?name=='FOUNDRY_HOSTED_AGENT_VERSION'].value | [0]" \
    --output tsv
)"
current_responses_endpoint="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --query "properties.template.containers[0].env[?name=='FOUNDRY_RESPONSES_ENDPOINT'].value | [0]" \
    --output tsv
)"
current_target_port="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --query 'properties.configuration.ingress.targetPort' \
    --output tsv
)"
if [[ "$current_image" == "$image" &&
      "$current_hosted_version" == "$hosted_agent_version" &&
      "$current_responses_endpoint" == "$responses_endpoint" &&
      "$current_target_port" == "8000" ]] &&
  curl --fail --silent --show-error --max-time 30 \
    "https://${frontend_fqdn}/backend-health" >/dev/null; then
  echo "Reusing healthy backend revision for image ${image} and hosted version ${hosted_agent_version}."
  echo "PUBLIC_BACKEND_IMAGE=$image"
  exit 0
fi

if [[ "$current_target_port" != "8000" ]]; then
  az containerapp ingress update \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --target-port 8000 \
    --output none
fi

az containerapp secret set \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --name "$backend_name" \
  --secrets "runtime-db-url=$runtime_database_url" \
  --output none

az containerapp update \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --name "$backend_name" \
  --image "$image" \
  --set-env-vars \
    "DATABASE_URL=secretref:runtime-db-url" \
    "RUNTIME_DATABASE_URL=secretref:runtime-db-url" \
    "DB_AUTH_MODE=password" \
    "DB_SCHEMA_MANAGED_EXTERNALLY=true" \
    "DB_SSLMODE=require" \
    "WORKFLOW_POOL_MAX_SIZE=4" \
    "LANGGRAPH_POOL_MAX_SIZE=2" \
    "UNDERWRITING_EXECUTION_MODE=hosted" \
    "AZURE_CLIENT_ID=${backend_identity_client_id}" \
    "AZURE_AI_PROJECT_ENDPOINT=${project_endpoint}" \
    "FOUNDRY_HOSTED_AGENT_NAME=${hosted_agent_name}" \
    "FOUNDRY_HOSTED_AGENT_VERSION=${hosted_agent_version}" \
    "FOUNDRY_RESPONSES_ENDPOINT=${responses_endpoint}" \
    "FRONTEND_ORIGIN=https://${frontend_fqdn}" \
  --output none

echo "PUBLIC_BACKEND_IMAGE=$image"
