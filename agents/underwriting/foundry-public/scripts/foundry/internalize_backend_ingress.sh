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

for binary in az azd curl python3; do
  command -v "$binary" >/dev/null 2>&1 || {
    echo "Missing required binary: $binary" >&2
    exit 1
  }
done

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
location="$(required_env AZURE_LOCATION)"
backend_name="$(required_env BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(required_env FRONTEND_CONTAINER_APP_NAME)"
confirmation="${1:-}"

[[ "$subscription_id" == "7df95e88-701c-4693-af77-3159f83b558d" ]] || {
  echo "Refusing migration outside the canonical Underwriting subscription." >&2
  exit 1
}
[[ "$resource_group" == "rg-langgraph-uw-foundry-public" && "$location" == "eastus2" ]] || {
  echo "Refusing migration outside rg-langgraph-uw-foundry-public/eastus2." >&2
  exit 1
}
[[ "$confirmation" == "INTERNALIZE-${backend_name}" ]] || {
  echo "Explicit confirmation required: make foundry-backend-internalize CONFIRM=INTERNALIZE-${backend_name}" >&2
  exit 2
}

az account set --subscription "$subscription_id" >/dev/null
actual_location="$(
  az group show \
    --subscription "$subscription_id" \
    --name "$resource_group" \
    --query location \
    --output tsv
)"
[[ "$actual_location" == "$location" ]] || {
  echo "Resource group location does not match the selected target." >&2
  exit 1
}

backend_json="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --output json
)"
frontend_json="$(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$frontend_name" \
    --output json
)"
backend_external="$(printf '%s' "$backend_json" | python3 -c 'import json,sys; print(str(json.load(sys.stdin)["properties"]["configuration"]["ingress"]["external"]).lower())')"
frontend_external="$(printf '%s' "$frontend_json" | python3 -c 'import json,sys; print(str(json.load(sys.stdin)["properties"]["configuration"]["ingress"]["external"]).lower())')"
backend_fqdn="$(printf '%s' "$backend_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["properties"]["configuration"]["ingress"]["fqdn"])')"
frontend_fqdn="$(printf '%s' "$frontend_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["properties"]["configuration"]["ingress"]["fqdn"])')"
frontend_url="https://${frontend_fqdn}"

[[ "$frontend_external" == "true" ]] || {
  echo "Frontend ingress must be external before backend migration." >&2
  exit 1
}
[[ "$backend_external" == "true" || "$backend_external" == "false" ]] || {
  echo "Backend ingress state is not recognized." >&2
  exit 1
}

if [[ "$backend_external" == "false" ]]; then
  curl --fail --silent --show-error --max-time 60 "$frontend_url/backend-health" >/dev/null
  curl --fail --silent --show-error --max-time 60 \
    "$frontend_url/api/v1/underwriting/runs?limit=1" >/dev/null
  if curl --fail --silent --show-error --max-time 10 "https://${backend_fqdn}/health" >/dev/null 2>&1; then
    echo "Backend is marked internal but remains directly publicly reachable." >&2
    exit 1
  fi
  echo "Backend ingress is already internal and same-origin proxy verification passed."
  exit 0
fi

"$ROOT_DIR/scripts/foundry/check_public_postgres_readiness.sh"
ALLOW_PUBLIC_BACKEND_FOR_MIGRATION=1 \
  "$ROOT_DIR/scripts/foundry/deploy_public_frontend.sh"

for _attempt in $(seq 1 30); do
  if curl --fail --silent --show-error --max-time 20 "$frontend_url/backend-health" >/dev/null &&
    curl --fail --silent --show-error --max-time 20 \
      "$frontend_url/api/v1/underwriting/runs?limit=1" >/dev/null; then
    proxy_ready=1
    break
  fi
  sleep 5
done
[[ "${proxy_ready:-0}" == "1" ]] || {
  echo "Proxy-capable frontend did not pass same-origin health/API checks; backend remains public." >&2
  exit 1
}

az containerapp ingress update \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --name "$backend_name" \
  --type internal \
  --target-port 8000 \
  --output none

"$ROOT_DIR/scripts/foundry/deploy_public_frontend.sh"

for _attempt in $(seq 1 30); do
  if curl --fail --silent --show-error --max-time 20 "$frontend_url/backend-health" >/dev/null &&
    curl --fail --silent --show-error --max-time 20 \
      "$frontend_url/api/v1/underwriting/runs?limit=1" >/dev/null; then
    internal_proxy_ready=1
    break
  fi
  sleep 5
done
[[ "${internal_proxy_ready:-0}" == "1" ]] || {
  echo "Backend was internalized but same-origin frontend/API verification failed." >&2
  exit 1
}

if curl --fail --silent --show-error --max-time 10 "https://${backend_fqdn}/health" >/dev/null 2>&1; then
  echo "Direct backend endpoint is still publicly reachable after internalization." >&2
  exit 1
fi

echo "Backend ingress migration completed: frontend is external, backend is internal, and /api is same-origin."
