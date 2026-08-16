#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

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

for command in az azd git jq; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required binary: $command" >&2
    exit 1
  }
done

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"
subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
registry_name="$(required_env AZURE_CONTAINER_REGISTRY_NAME)"
registry_endpoint="$(required_env AZURE_CONTAINER_REGISTRY_ENDPOINT)"
backend_name="$(required_env BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(required_env FRONTEND_CONTAINER_APP_NAME)"
image_repository="$(required_env FRONTEND_IMAGE_REPOSITORY)"

[[ "$subscription_id" == "7df95e88-701c-4693-af77-3159f83b558d" ]] &&
  [[ "$resource_group" == "rg-langgraph-ora-foundry-public" ]] || {
  echo "Frontend deployment requires the canonical public target." >&2
  exit 1
}

az account set --subscription "$subscription_id"
backend_fqdn="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --query properties.configuration.ingress.fqdn \
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
  --file "$ROOT_DIR/frontend/Dockerfile" \
  "$ROOT_DIR/frontend"
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
az containerapp update \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --name "$frontend_name" \
  --image "$image" \
  --set-env-vars "API_BASE=" "NGINX_API_UPSTREAM=https://${backend_fqdn}" \
  --output none
az containerapp ingress update \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --name "$frontend_name" \
  --target-port 5173 \
  --transport http \
  --output none

release_id="${FOUNDRY_RELEASE_ID:-manual-frontend-deploy}"
release_started_at="${FOUNDRY_RELEASE_STARTED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
revision_name="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$frontend_name" \
    --query properties.latestRevisionName \
    --output tsv
)"
metadata_file="${PUBLIC_FRONTEND_DEPLOYMENT_METADATA_FILE:-$ROOT_DIR/backend/.foundry/results/frontend-deployment.json}"
mkdir -p "$(dirname "$metadata_file")"
jq -n \
  --arg release_id "$release_id" \
  --arg release_started_at "$release_started_at" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg container_app "$frontend_name" \
  --arg revision "$revision_name" \
  --arg tagged_image "$tagged_image" \
  --arg image "$image" \
  '{
    schema_version: 1,
    evidence_type: "component_deployment",
    component: "frontend",
    status: "deployed",
    release_id: $release_id,
    release_started_at: $release_started_at,
    generated_at: $generated_at,
    container_app: $container_app,
    revision: $revision,
    tagged_image: $tagged_image,
    image: $image,
    external: true,
    same_origin_proxy: true
  }' >"$metadata_file"

echo "PUBLIC_FRONTEND_IMAGE=$image"
echo "PUBLIC_FRONTEND_REVISION=$revision_name"
