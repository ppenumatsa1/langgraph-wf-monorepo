#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

for command in az azd git jq; do
  require_command "$command"
done
assert_target

subscription_id="$(required_azd_value AZURE_SUBSCRIPTION_ID)"
registry_name="$(required_azd_value AZURE_CONTAINER_REGISTRY_NAME)"
registry_endpoint="$(required_azd_value AZURE_CONTAINER_REGISTRY_ENDPOINT)"
backend_repository="$(required_azd_value BACKEND_IMAGE_REPOSITORY)"
frontend_repository="$(required_azd_value FRONTEND_IMAGE_REPOSITORY)"
source_revision="$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD 2>/dev/null || true)"
[[ -n "$source_revision" ]] || source_revision=uncommitted
image_tag="${source_revision}-$(date -u +%Y%m%d%H%M%S)"

az acr build --subscription "$subscription_id" --registry "$registry_name" \
  --image "${backend_repository}:${image_tag}" --file "$ROOT_DIR/backend/Dockerfile" \
  "$ROOT_DIR/backend" --no-logs &
backend_pid=$!
az acr build --subscription "$subscription_id" --registry "$registry_name" \
  --image "${frontend_repository}:${image_tag}" --file "$ROOT_DIR/frontend/Dockerfile" \
  "$ROOT_DIR/frontend" --no-logs &
frontend_pid=$!
wait "$backend_pid"
wait "$frontend_pid"

backend_digest="$(az acr repository show --subscription "$subscription_id" --name "$registry_name" \
  --image "${backend_repository}:${image_tag}" --query digest -o tsv)"
frontend_digest="$(az acr repository show --subscription "$subscription_id" --name "$registry_name" \
  --image "${frontend_repository}:${image_tag}" --query digest -o tsv)"
[[ "$backend_digest" =~ ^sha256:[0-9a-f]{64}$ && "$frontend_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || {
  echo "ACR did not return immutable image digests." >&2
  exit 1
}

evidence_dir="$(release_evidence_dir)"
mkdir -p "$evidence_dir"
jq -n \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg backend "${registry_endpoint}/${backend_repository}@${backend_digest}" \
  --arg frontend "${registry_endpoint}/${frontend_repository}@${frontend_digest}" \
  '{status:"passed",generated_at:$generated_at,backend_image:$backend,frontend_image:$frontend}' \
  >"$evidence_dir/images.json"
