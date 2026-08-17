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
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null
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

for command in az azd git; do
  require_bin "$command"
done
[[ -n "${RELEASE_ID:-}" && -n "${FOUNDRY_RELEASE_EVIDENCE_DIR:-}" && -n "${FOUNDRY_RELEASE_LOG_DIR:-}" ]] || {
  echo "RELEASE_ID and canonical release paths are required." >&2
  exit 2
}

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"
"$ROOT_DIR/scripts/foundry/sync_hosted_source.sh"

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
registry_name="$(required_env AZURE_CONTAINER_REGISTRY_NAME)"
registry_endpoint="$(required_env AZURE_CONTAINER_REGISTRY_ENDPOINT)"
backend_repository="$(required_env BACKEND_IMAGE_REPOSITORY)"
frontend_repository="$(required_env FRONTEND_IMAGE_REPOSITORY)"
hosted_repository="underwriting-hosted"
tag="$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD)-$(date -u +%Y%m%d%H%M%S)"
image_env="$FOUNDRY_RELEASE_EVIDENCE_DIR/release-images.env"

source_fingerprint() {
  git -C "$ROOT_DIR" ls-tree -r HEAD -- "$@" | sha256sum | awk '{print $1}'
}

backend_fingerprint="$(
  source_fingerprint .dockerignore backend/Dockerfile backend/pyproject.toml backend/app
)"
frontend_fingerprint="$(source_fingerprint frontend)"
hosted_fingerprint="$(
  source_fingerprint \
    backend/Dockerfile.hosted \
    backend/pyproject.toml \
    backend/app \
    backend/foundry \
    .dockerignore \
    scripts/foundry/sync_hosted_source.sh
)"

write_image_env() {
  local backend_image="$1"
  local frontend_image="$2"
  local hosted_image="$3"
  umask 077
  {
    printf 'PUBLIC_BACKEND_PREBUILT_IMAGE=%q\n' "$backend_image"
    printf 'PUBLIC_FRONTEND_PREBUILT_IMAGE=%q\n' "$frontend_image"
    printf 'HOSTED_AGENT_PREBUILT_IMAGE=%q\n' "$hosted_image"
  } >"$image_env"
}

validate_prebuilt_image() {
  local repository="$1"
  local image="$2"
  local source_fingerprint="$3"
  local expected_prefix="${registry_endpoint}/${repository}@"
  local digest
  local resolved
  local source_tag="source-${source_fingerprint}"

  [[ "$image" == "${expected_prefix}"sha256:* ]] || {
    echo "Prebuilt image must use the configured registry, repository, and immutable digest: ${repository}." >&2
    exit 1
  }
  digest="${image#"$expected_prefix"}"
  [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] || {
    echo "Prebuilt image digest is invalid: ${repository}." >&2
    exit 1
  }
  resolved="$(
    az acr repository show \
      --subscription "$subscription_id" \
      --name "$registry_name" \
      --image "${repository}@${digest}" \
      --query digest \
      --output tsv
  )"
  [[ "$resolved" == "$digest" ]] || {
    echo "Prebuilt image digest was not found in ACR: ${repository}." >&2
    exit 1
  }
  if ! az acr repository show \
    --subscription "$subscription_id" \
    --name "$registry_name" \
    --image "${repository}@${digest}" \
    --query 'tags[]' \
    --output tsv | grep -Fxq "$source_tag"; then
    echo "Prebuilt image is not bound to the current ${repository} source fingerprint." >&2
    exit 1
  fi
}

prebuilt_backend="${PUBLIC_BACKEND_PREBUILT_IMAGE:-}"
prebuilt_frontend="${PUBLIC_FRONTEND_PREBUILT_IMAGE:-}"
prebuilt_hosted="${HOSTED_AGENT_PREBUILT_IMAGE:-}"
if [[ -n "$prebuilt_backend" ]]; then
  validate_prebuilt_image "$backend_repository" "$prebuilt_backend" "$backend_fingerprint"
fi
if [[ -n "$prebuilt_frontend" ]]; then
  validate_prebuilt_image "$frontend_repository" "$prebuilt_frontend" "$frontend_fingerprint"
fi
if [[ -n "$prebuilt_hosted" ]]; then
  validate_prebuilt_image "$hosted_repository" "$prebuilt_hosted" "$hosted_fingerprint"
fi
if [[ -n "$prebuilt_backend" && -n "$prebuilt_frontend" && -n "$prebuilt_hosted" ]]; then
  write_image_env "$prebuilt_backend" "$prebuilt_frontend" "$prebuilt_hosted"
  echo "Reused verified immutable backend, frontend, and hosted-agent images."
  exit 0
fi

build_acr_image() {
  local repository="$1"
  local dockerfile="$2"
  local context="$3"
  local log_file="$4"
  local source_fingerprint="$5"
  az acr build \
    --subscription "$subscription_id" \
    --registry "$registry_name" \
    --image "${repository}:${tag}" \
    --image "${repository}:source-${source_fingerprint}" \
    --file "$dockerfile" \
    "$context" >"$log_file" 2>&1
}

pids=()
if [[ -z "$prebuilt_backend" ]]; then
  build_acr_image \
    "$backend_repository" \
    "$ROOT_DIR/backend/Dockerfile" \
    "$ROOT_DIR" \
    "$FOUNDRY_RELEASE_LOG_DIR/backend-image-build.log" \
    "$backend_fingerprint" &
  pids+=("$!")
fi
if [[ -z "$prebuilt_hosted" ]]; then
  build_acr_image \
    "$hosted_repository" \
    "$FOUNDRY_DIR/agent/Dockerfile" \
    "$FOUNDRY_DIR/agent" \
    "$FOUNDRY_RELEASE_LOG_DIR/hosted-image-build.log" \
    "$hosted_fingerprint" &
  pids+=("$!")
fi
if [[ -z "$prebuilt_frontend" ]]; then
  build_acr_image \
    "$frontend_repository" \
    "$ROOT_DIR/frontend/Dockerfile" \
    "$ROOT_DIR/frontend" \
    "$FOUNDRY_RELEASE_LOG_DIR/frontend-image-build.log" \
    "$frontend_fingerprint" &
  pids+=("$!")
fi

status=0
for pid in "${pids[@]}"; do
  wait "$pid" || status=1
done
(( status == 0 )) || {
  echo "One or more release image builds failed; inspect canonical release logs." >&2
  exit 1
}

resolve_image() {
  local repository="$1"
  local digest
  digest="$(
    az acr repository show \
      --subscription "$subscription_id" \
      --name "$registry_name" \
      --image "${repository}:${tag}" \
      --query digest \
      --output tsv
  )"
  [[ "$digest" == sha256:* ]] || {
    echo "Unable to resolve immutable digest for ${repository}:${tag}." >&2
    exit 1
  }
  printf '%s/%s@%s' "$registry_endpoint" "$repository" "$digest"
}

backend_image="$prebuilt_backend"
frontend_image="$prebuilt_frontend"
hosted_image="$prebuilt_hosted"
if [[ -z "$backend_image" ]]; then
  backend_image="$(resolve_image "$backend_repository")"
fi
if [[ -z "$frontend_image" ]]; then
  frontend_image="$(resolve_image "$frontend_repository")"
fi
if [[ -z "$hosted_image" ]]; then
  hosted_image="$(resolve_image "$hosted_repository")"
fi
write_image_env "$backend_image" "$frontend_image" "$hosted_image"

echo "Resolved immutable backend, frontend, and hosted-agent images; unchanged prebuilt digests were reused."
