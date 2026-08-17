#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -n "${RELEASE_ID:-}" ]]; then
  . "$ROOT_DIR/scripts/foundry/release_paths.sh"
  release_paths_configure "$ROOT_DIR"
fi
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
PYTHON="$ROOT_DIR/.venv/bin/python"
EVIDENCE_FILE="${FOUNDRY_VERIFY_EVIDENCE_FILE:-$ROOT_DIR/backend/.foundry/results/foundry-verify.json}"

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

for binary in az azd curl jq; do
  command -v "$binary" >/dev/null 2>&1 || {
    echo "Missing required binary: $binary" >&2
    exit 1
  }
done
[[ -x "$PYTHON" ]] || {
  echo "Project virtual environment is required; run make install first." >&2
  exit 1
}

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
location="$(required_env AZURE_LOCATION)"
backend_name="$(required_env BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(required_env FRONTEND_CONTAINER_APP_NAME)"
project_endpoint="$(required_env AZURE_AI_PROJECT_ENDPOINT)"
hosted_agent_name="$(required_env AGENT_UNDERWRITING_HOSTED_NAME)"
hosted_agent_version="$(required_env AGENT_UNDERWRITING_HOSTED_VERSION)"
runtime_connection_name="$(required_env FOUNDRY_RUNTIME_CONNECTION_NAME)"
registry_endpoint="$(required_env AZURE_CONTAINER_REGISTRY_ENDPOINT)"
backend_repository="$(required_env BACKEND_IMAGE_REPOSITORY)"
frontend_repository="$(required_env FRONTEND_IMAGE_REPOSITORY)"
database_url="$(required_env DATABASE_URL)"
runtime_database_url="$(required_env RUNTIME_DATABASE_URL)"

[[ "$subscription_id" == "7df95e88-701c-4693-af77-3159f83b558d" &&
  "$resource_group" == "rg-langgraph-uw-foundry-public" &&
  "$location" == "eastus2" ]] || {
  echo "Selected environment is not the canonical Underwriting target." >&2
  exit 1
}
[[ "$database_url" == "$runtime_database_url" ]] || {
  echo "DATABASE_URL and RUNTIME_DATABASE_URL are not identical in the selected environment." >&2
  exit 1
}
[[ "$runtime_connection_name" == "underwritingruntimesecrets" ]] || {
  echo "Unexpected Underwriting runtime-secret connection name." >&2
  exit 1
}
az account set --subscription "$subscription_id" >/dev/null

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
backend_external="$(jq -r '.properties.configuration.ingress.external' <<<"$backend_json")"
frontend_external="$(jq -r '.properties.configuration.ingress.external' <<<"$frontend_json")"
backend_fqdn="$(jq -r '.properties.configuration.ingress.fqdn' <<<"$backend_json")"
frontend_fqdn="$(jq -r '.properties.configuration.ingress.fqdn' <<<"$frontend_json")"
backend_revision="$(jq -r '.properties.latestReadyRevisionName // empty' <<<"$backend_json")"
frontend_revision="$(jq -r '.properties.latestReadyRevisionName // empty' <<<"$frontend_json")"
backend_image="$(jq -r '.properties.template.containers[0].image // empty' <<<"$backend_json")"
frontend_image="$(jq -r '.properties.template.containers[0].image // empty' <<<"$frontend_json")"
backend_schema_mode="$(
  jq -r '
    [.properties.template.containers[0].env[]? | select(.name == "DB_SCHEMA_MANAGED_EXTERNALLY") | .value][0] // ""
  ' <<<"$backend_json"
)"
backend_database_secret="$(
  jq -r '
    [.properties.template.containers[0].env[]? | select(.name == "DATABASE_URL") | .secretRef][0] // ""
  ' <<<"$backend_json"
)"
backend_runtime_database_secret="$(
  jq -r '
    [.properties.template.containers[0].env[]? | select(.name == "RUNTIME_DATABASE_URL") | .secretRef][0] // ""
  ' <<<"$backend_json"
)"
frontend_upstream="$(
  jq -r '
    [.properties.template.containers[0].env[]? | select(.name == "NGINX_API_UPSTREAM") | .value][0] // ""
  ' <<<"$frontend_json"
)"

[[ "$backend_external" == "false" && "$frontend_external" == "true" ]] || {
  echo "Container Apps ingress topology is not frontend-external/backend-internal." >&2
  exit 1
}
[[ -n "$backend_revision" && -n "$frontend_revision" &&
  -n "$backend_image" && -n "$frontend_image" ]] || {
  echo "Container Apps ready revisions/images are incomplete." >&2
  exit 1
}
[[ "$backend_image" == "${registry_endpoint}/${backend_repository}@"* &&
  "$backend_image" == *@sha256:* &&
  "$frontend_image" == "${registry_endpoint}/${frontend_repository}@"* &&
  "$frontend_image" == *@sha256:* ]] || {
  echo "Container Apps ready images are not from the configured Underwriting repositories." >&2
  exit 1
}
[[ "$backend_schema_mode" == "true" ]] || {
  echo "Backend revision does not enable external schema management." >&2
  exit 1
}
[[ -n "$backend_database_secret" &&
  "$backend_database_secret" == "$backend_runtime_database_secret" ]] || {
  echo "Backend DATABASE_URL and RUNTIME_DATABASE_URL do not use the same secret." >&2
  exit 1
}
[[ "$frontend_upstream" == "https://${backend_fqdn}" ]] || {
  echo "Frontend NGINX_API_UPSTREAM does not target the internal backend FQDN." >&2
  exit 1
}

frontend_url="https://${frontend_fqdn}"
curl --fail --silent --show-error --max-time 60 "$frontend_url/healthz" >/dev/null
curl --fail --silent --show-error --max-time 60 "$frontend_url/backend-health" >/dev/null
curl --fail --silent --show-error --max-time 60 \
  "$frontend_url/api/v1/underwriting/runs?limit=1" >/dev/null

revision_is_running() {
  local app_name="$1"
  local revision="$2"
  local state
  state="$(
    az containerapp revision show \
      --subscription "$subscription_id" \
      --resource-group "$resource_group" \
      --name "$app_name" \
      --revision "$revision" \
      --query properties.runningState \
      --output tsv
  )"
  [[ "$state" == "Running" || "$state" == "RunningAtMaxScale" ]]
}

for attempt in $(seq 1 6); do
  backend_running=false
  frontend_running=false
  revision_is_running "$backend_name" "$backend_revision" && backend_running=true
  revision_is_running "$frontend_name" "$frontend_revision" && frontend_running=true
  if [[ "$backend_running" == "true" && "$frontend_running" == "true" ]]; then
    break
  fi
  [[ "$attempt" -lt 6 ]] || {
    echo "Container Apps ready revisions did not reach Running state." >&2
    exit 1
  }
  sleep 10
done
if curl --fail --silent --show-error --max-time 10 "https://${backend_fqdn}/health" >/dev/null 2>&1; then
  echo "Backend is still directly reachable from the public internet." >&2
  exit 1
fi

"$ROOT_DIR/scripts/foundry/check_public_postgres_readiness.sh" >/dev/null
"$ROOT_DIR/scripts/foundry/verify_project_appinsights_connection.sh" >/dev/null

connection_url="https://management.azure.com/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/$(required_env FOUNDRY_ACCOUNT_NAME)/projects/$(required_env FOUNDRY_PROJECT_NAME)/connections/${runtime_connection_name}?api-version=2025-04-01-preview"
connection_metadata="$(
  az rest \
    --method get \
    --url "$connection_url" \
    --query '{category:properties.category,authType:properties.authType,target:properties.target}' \
    --output json
)"
jq -e '
  .category == "CustomKeys"
  and .authType == "CustomKeys"
  and .target == "https://underwriting-runtime-secrets.local"
' >/dev/null <<<"$connection_metadata" || {
  echo "Underwriting runtime-secret connection metadata verification failed." >&2
  exit 1
}

hosted_json="$(
  AZURE_AI_PROJECT_ENDPOINT="$project_endpoint" \
  HOSTED_AGENT_NAME="$hosted_agent_name" \
  HOSTED_AGENT_VERSION="$hosted_agent_version" \
  FOUNDRY_RUNTIME_CONNECTION_NAME="$runtime_connection_name" \
    "$PYTHON" "$ROOT_DIR/scripts/foundry/inspect_hosted_agent.py"
)"
jq -e '
  .status == "active"
  and (.image | length > 0)
  and .db_schema_managed_externally
  and .database_url_placeholder
  and .runtime_database_url_placeholder
  and .database_url_parity
  and .application_insights_configured
' >/dev/null <<<"$hosted_json" || {
  echo "Hosted agent version/image/runtime configuration verification failed." >&2
  exit 1
}
hosted_image="$(jq -r '.image' <<<"$hosted_json")"
unset database_url runtime_database_url
[[ "$hosted_image" == "${registry_endpoint}/underwriting-hosted@"* &&
  "$hosted_image" == *@sha256:* ]] || {
  echo "Hosted agent image is not from the configured Underwriting repository." >&2
  exit 1
}

mkdir -p "$(dirname "$EVIDENCE_FILE")"
jq -n \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg subscription_id "$subscription_id" \
  --arg resource_group "$resource_group" \
  --arg location "$location" \
  --arg frontend_url "$frontend_url" \
  --arg backend_name "$backend_name" \
  --arg backend_revision "$backend_revision" \
  --arg backend_image "$backend_image" \
  --arg frontend_name "$frontend_name" \
  --arg frontend_revision "$frontend_revision" \
  --arg frontend_image "$frontend_image" \
  --argjson hosted "$hosted_json" \
  '{
    generated_at: $generated_at,
    target: {
      subscription_id: $subscription_id,
      resource_group: $resource_group,
      location: $location
    },
    topology: {
      frontend_url: $frontend_url,
      frontend_external: true,
      backend_internal: true,
      same_origin_health: true,
      same_origin_api: true,
      direct_backend_publicly_reachable: false
    },
    container_apps: {
      backend: {name: $backend_name, revision: $backend_revision, image: $backend_image},
      frontend: {name: $frontend_name, revision: $frontend_revision, image: $frontend_image}
    },
    hosted_agent: $hosted,
    runtime_secret_connection: {
      name: $hosted.runtime_connection_name,
      category: "CustomKeys",
      database_url_metadata_is_placeholder: true
    },
    application_insights_connection: true,
    runtime_database: {
      url_parity: true,
      required_schema_ready: true,
      schema_managed_externally: true
    }
  }' >"$EVIDENCE_FILE"

echo "Foundry release verification passed. Evidence written to ${EVIDENCE_FILE}."
