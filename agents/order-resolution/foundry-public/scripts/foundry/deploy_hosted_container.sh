#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

require_env() {
  local key="$1"
  local value="$2"
  if [[ -z "$value" ]]; then
    echo "Missing required AZD environment value: $key" >&2
    exit 1
  fi
  printf '%s\n' "$value"
}

require_bin az
require_bin azd
require_bin git
require_bin jq

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
PYTHON="$ROOT_DIR/backend/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Backend virtual environment is required; run make ensure-backend-env." >&2
  exit 1
fi

cd "$FOUNDRY_DIR"
get_env() {
  local value
  if ! value="$(
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value "$1" 2>/dev/null
  )"; then
    return 0
  fi
  printf '%s' "$value"
}

registry_name="$(require_env AZURE_CONTAINER_REGISTRY_NAME "$(get_env AZURE_CONTAINER_REGISTRY_NAME)")"
registry_endpoint="$(require_env AZURE_CONTAINER_REGISTRY_ENDPOINT "$(get_env AZURE_CONTAINER_REGISTRY_ENDPOINT)")"
subscription_id="$(require_env AZURE_SUBSCRIPTION_ID "$(get_env AZURE_SUBSCRIPTION_ID)")"
resource_group="$(require_env AZURE_RESOURCE_GROUP "$(get_env AZURE_RESOURCE_GROUP)")"
foundry_account="$(require_env FOUNDRY_ACCOUNT_NAME "$(get_env FOUNDRY_ACCOUNT_NAME)")"
foundry_project="$(require_env FOUNDRY_PROJECT_NAME "$(get_env FOUNDRY_PROJECT_NAME)")"
project_endpoint="$(require_env FOUNDRY_PROJECTS_ENDPOINT "$(get_env FOUNDRY_PROJECTS_ENDPOINT)")"
agent_name="$(require_env HOSTED_AGENT_NAME "$(get_env HOSTED_AGENT_NAME)")"
model_name="$(require_env FOUNDRY_MODEL_DEPLOYMENT_NAME "$(get_env FOUNDRY_MODEL_DEPLOYMENT_NAME)")"
runtime_database_url="$(require_env RUNTIME_DATABASE_URL "$(get_env RUNTIME_DATABASE_URL)")"
postgres_server_name="$(require_env POSTGRES_SERVER_NAME "$(get_env POSTGRES_SERVER_NAME)")"
runtime_connection_name="$(
  require_env FOUNDRY_RUNTIME_CONNECTION_NAME "$(get_env FOUNDRY_RUNTIME_CONNECTION_NAME)"
)"

[[ "$subscription_id" == "7df95e88-701c-4693-af77-3159f83b558d" ]] &&
  [[ "$resource_group" == "rg-langgraph-ora-foundry-public" ]] || {
  echo "Hosted-agent deployment requires the canonical public target." >&2
  exit 1
}
if [[ "$runtime_database_url" != *"${postgres_server_name}.postgres.database.azure.com"* ]]; then
  echo "RUNTIME_DATABASE_URL must target ${postgres_server_name}.postgres.database.azure.com." >&2
  exit 1
fi
if [[ "$runtime_database_url" != *"sslmode=require"* ]]; then
  echo "RUNTIME_DATABASE_URL must require TLS." >&2
  exit 1
fi
[[ "$runtime_connection_name" == "orderresolutionruntimesecrets" ]] || {
  echo "Unexpected Foundry runtime connection name: $runtime_connection_name" >&2
  exit 1
}

az account set --subscription "$subscription_id"
connection_url="https://management.azure.com/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/${foundry_account}/projects/${foundry_project}/connections/${runtime_connection_name}?api-version=2025-04-01-preview"
connection_metadata="$(
  az rest \
    --subscription "$subscription_id" \
    --method get \
    --url "$connection_url" \
    --query '{category:properties.category,auth_type:properties.authType}' \
    --output json
)"
jq -e '.category == "CustomKeys" and .auth_type == "CustomKeys"' \
  <<<"$connection_metadata" >/dev/null || {
  echo "Foundry runtime secret connection is missing or misconfigured." >&2
  exit 1
}

image_repository="${HOSTED_AGENT_IMAGE_REPOSITORY:-order-resolution-hosted}"
source_revision="$(git -C "$ROOT_DIR" rev-parse --short=12 HEAD 2>/dev/null || true)"
[[ -n "$source_revision" ]] || source_revision=uncommitted
image_tag="${HOSTED_AGENT_IMAGE_TAG:-${source_revision}-$(date -u +%Y%m%d%H%M%S)}"
tagged_image="${registry_endpoint}/${image_repository}:${image_tag}"

az acr build \
  --subscription "$subscription_id" \
  --registry "$registry_name" \
  --image "${image_repository}:${image_tag}" \
  --file "$FOUNDRY_DIR/agent/Dockerfile" \
  "$FOUNDRY_DIR/agent"
image_digest="$(
  az acr repository show \
    --subscription "$subscription_id" \
    --name "$registry_name" \
    --image "${image_repository}:${image_tag}" \
    --query digest \
    --output tsv
)"
[[ "$image_digest" =~ ^sha256:[0-9a-f]{64}$ ]] || {
  echo "Hosted-agent image digest was not returned by ACR." >&2
  exit 1
}
image="${registry_endpoint}/${image_repository}@${image_digest}"

export FOUNDRY_PROJECT_ENDPOINT="$project_endpoint"
export FOUNDRY_HOSTED_AGENT_NAME="$agent_name"
export FOUNDRY_IMAGE="$image"
export FOUNDRY_MODEL_DEPLOYMENT_NAME="$model_name"
export FOUNDRY_RUNTIME_CONNECTION_NAME="$runtime_connection_name"
export APP_ENV="$(require_env APP_ENV "$(get_env APP_ENV)")"
export STORE_PROVIDER="$(require_env STORE_PROVIDER "$(get_env STORE_PROVIDER)")"
export DB_SCHEMA_MANAGED_EXTERNALLY="$(require_env DB_SCHEMA_MANAGED_EXTERNALLY "$(get_env DB_SCHEMA_MANAGED_EXTERNALLY)")"
if [[ "${DB_SCHEMA_MANAGED_EXTERNALLY,,}" != "true" ]]; then
  echo "Hosted agent requires DB_SCHEMA_MANAGED_EXTERNALLY=true." >&2
  exit 1
fi
export ENABLE_TELEMETRY="$(require_env ENABLE_TELEMETRY "$(get_env ENABLE_TELEMETRY)")"
export ENABLE_INSTRUMENTATION="$(require_env ENABLE_INSTRUMENTATION "$(get_env ENABLE_INSTRUMENTATION)")"
export OTEL_SERVICE_NAME="$(
  require_env FOUNDRY_HOSTED_OTEL_SERVICE_NAME "$(get_env FOUNDRY_HOSTED_OTEL_SERVICE_NAME)"
)"
export OTEL_SERVICE_NAMESPACE="$(
  require_env FOUNDRY_OTEL_SERVICE_NAMESPACE "$(get_env FOUNDRY_OTEL_SERVICE_NAMESPACE)"
)"
export OTEL_RECORD_CONTENT="$(require_env OTEL_RECORD_CONTENT "$(get_env OTEL_RECORD_CONTENT)")"
export OTEL_EXPORTER_OTLP_TRACES_ENDPOINT="$(get_env OTEL_EXPORTER_OTLP_TRACES_ENDPOINT)"
export TRACE_EVALUATION_RECORD_CONTENT="$(require_env FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT "$(get_env FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT)")"
deployment_output="$("$PYTHON" "$ROOT_DIR/scripts/foundry/deploy_hosted_container.py")"
printf '%s\n' "$deployment_output"
agent_version="$(printf '%s\n' "$deployment_output" | sed -n 's/^HOSTED_AGENT_VERSION=//p' | tail -n 1)"
principal_id="$(printf '%s\n' "$deployment_output" | sed -n 's/^HOSTED_AGENT_PRINCIPAL_ID=//p' | tail -n 1)"
if [[ -z "$agent_version" ]]; then
  echo "Hosted agent deployment did not report an active version." >&2
  exit 1
fi
if [[ -z "$principal_id" ]]; then
  echo "Hosted agent deployment did not report its managed identity principal ID." >&2
  exit 1
fi

HOSTED_AGENT_PRINCIPAL_ID="$principal_id" \
  "$ROOT_DIR/scripts/foundry/ensure_hosted_agent_rbac.sh"

agent_endpoint="${project_endpoint}/agents/${agent_name}/endpoint/protocols/openai/responses?api-version=v1"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AGENT_ORDER_RESOLUTION_HOSTED_NAME "$agent_name" >/dev/null
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AGENT_ORDER_RESOLUTION_HOSTED_VERSION "$agent_version" >/dev/null
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AGENT_ORDER_RESOLUTION_HOSTED_RESPONSES_ENDPOINT "$agent_endpoint" >/dev/null
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AGENT_ORDER_RESOLUTION_HOSTED_IMAGE "$image" >/dev/null
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env set AGENT_ORDER_RESOLUTION_HOSTED_PRINCIPAL_ID "$principal_id" >/dev/null

release_id="${FOUNDRY_RELEASE_ID:-manual-hosted-deploy}"
release_started_at="${FOUNDRY_RELEASE_STARTED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
metadata_file="${HOSTED_AGENT_DEPLOYMENT_METADATA_FILE:-$ROOT_DIR/backend/.foundry/results/hosted-agent-deployment.json}"
mkdir -p "$(dirname "$metadata_file")"
jq -n \
  --arg release_id "$release_id" \
  --arg release_started_at "$release_started_at" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg name "$agent_name" \
  --arg version "$agent_version" \
  --arg tagged_image "$tagged_image" \
  --arg image "$image" \
  --arg principal_id "$principal_id" \
  --arg runtime_connection_name "$runtime_connection_name" \
  --arg role "Cognitive Services OpenAI User" \
  '{
    schema_version: 1,
    evidence_type: "component_deployment",
    component: "hosted_agent",
    status: "deployed",
    release_id: $release_id,
    release_started_at: $release_started_at,
    generated_at: $generated_at,
    name: $name,
    version: $version,
    tagged_image: $tagged_image,
    image: $image,
    principal_id: $principal_id,
    runtime_connection_name: $runtime_connection_name,
    required_role: $role,
    schema_managed_externally: true
  }' >"$metadata_file"
echo "Hosted agent image deployment completed: ${image}"
