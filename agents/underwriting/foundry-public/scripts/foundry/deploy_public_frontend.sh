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

if [[ -z "${PUBLIC_FRONTEND_PREBUILT_IMAGE:-}" ]]; then
  "$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"
fi

resource_group="$(required_env AZURE_RESOURCE_GROUP)"
subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
location="$(required_env AZURE_LOCATION)"
registry_name="$(required_env AZURE_CONTAINER_REGISTRY_NAME)"
registry_endpoint="$(required_env AZURE_CONTAINER_REGISTRY_ENDPOINT)"
backend_name="$(required_env BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(required_env FRONTEND_CONTAINER_APP_NAME)"
image_repository="$(required_env FRONTEND_IMAGE_REPOSITORY)"
az account set --subscription "$subscription_id" >/dev/null
[[ "$subscription_id" == "7df95e88-701c-4693-af77-3159f83b558d" &&
  "$resource_group" == "rg-langgraph-uw-foundry-public" &&
  "${location,,}" == "eastus2" ]] || {
  echo "Frontend deployment requires the canonical Underwriting public target." >&2
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
if [[ "$backend_external" != "false" && "${ALLOW_PUBLIC_BACKEND_FOR_MIGRATION:-0}" != "1" ]]; then
  echo "Backend ingress must already be internal. Use the one-time foundry-backend-internalize command for migration." >&2
  exit 1
fi
frontend_external="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$frontend_name" \
    --query 'properties.configuration.ingress.external' \
    --output tsv
)"
frontend_external="${frontend_external,,}"
if [[ "$frontend_external" != "true" ]]; then
  echo "Frontend ingress must already be external; routine app-only deployment does not mutate topology." >&2
  exit 1
fi
backend_fqdn="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --query 'properties.configuration.ingress.fqdn' \
    --output tsv
)"
image="${PUBLIC_FRONTEND_PREBUILT_IMAGE:-}"
if [[ -z "$image" ]]; then
  require_bin docker
  image_tag="$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)"
  tagged_image="${registry_endpoint}/${image_repository}:${image_tag}"
  az acr login \
    --subscription "$subscription_id" \
    --name "$registry_name" \
    --output none
  docker build \
    --file "$ROOT_DIR/frontend/Dockerfile" \
    --tag "$tagged_image" \
    "$ROOT_DIR/frontend"
  docker push "$tagged_image"
  image_digest="$(
    az acr repository show \
      --subscription "$subscription_id" \
      --name "$registry_name" \
      --image "${image_repository}:${image_tag}" \
      --query digest \
      --output tsv
  )"
  [[ "$image_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || {
    echo "Frontend image digest was not returned by ACR." >&2
    exit 1
  }
  image="${registry_endpoint}/${image_repository}@${image_digest}"
elif [[ "$image" != *@sha256:* ]]; then
  echo "PUBLIC_FRONTEND_PREBUILT_IMAGE must be pinned by digest." >&2
  exit 1
fi

expected_upstream="https://${backend_fqdn}"
current_image="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$frontend_name" \
    --query 'properties.template.containers[0].image' \
    --output tsv
)"
current_upstream="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$frontend_name" \
    --query "properties.template.containers[0].env[?name=='NGINX_API_UPSTREAM'].value | [0]" \
    --output tsv
)"
frontend_url="https://$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$frontend_name" \
    --query 'properties.configuration.ingress.fqdn' \
    --output tsv
)"
if [[ "$current_image" == "$image" && "$current_upstream" == "$expected_upstream" ]] &&
  curl --fail --silent --show-error --max-time 30 "$frontend_url/healthz" >/dev/null &&
  curl --fail --silent --show-error --max-time 30 "$frontend_url/backend-health" >/dev/null; then
  echo "Reusing healthy frontend revision for image ${image}."
  echo "PUBLIC_FRONTEND_IMAGE=$image"
  exit 0
fi

az containerapp update \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --name "$frontend_name" \
  --image "$image" \
  --set-env-vars "NGINX_API_UPSTREAM=${expected_upstream}" \
  --output none

echo "PUBLIC_FRONTEND_IMAGE=$image"
