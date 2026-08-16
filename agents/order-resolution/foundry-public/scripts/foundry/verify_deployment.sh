#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
RESULTS_DIR="$ROOT_DIR/backend/.foundry/results"
EVIDENCE_FILE="${FOUNDRY_DEPLOYMENT_VERIFICATION_FILE:-$RESULTS_DIR/deployment-verification.json}"
BACKEND_METADATA_FILE="${PUBLIC_BACKEND_DEPLOYMENT_METADATA_FILE:-$RESULTS_DIR/backend-deployment.json}"
FRONTEND_METADATA_FILE="${PUBLIC_FRONTEND_DEPLOYMENT_METADATA_FILE:-$RESULTS_DIR/frontend-deployment.json}"
HOSTED_METADATA_FILE="${HOSTED_AGENT_DEPLOYMENT_METADATA_FILE:-$RESULTS_DIR/hosted-agent-deployment.json}"
RUNTIME_CONNECTION_METADATA_FILE="${FOUNDRY_RUNTIME_CONNECTION_METADATA_FILE:-$RESULTS_DIR/runtime-connection-deployment.json}"
CONTEXT_FILE="${FOUNDRY_RELEASE_CONTEXT_FILE:-$RESULTS_DIR/release-context.json}"

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

required_env() {
  local name="$1"
  local line value
  line="$(printf '%s\n' "$AZD_ENV_VALUES" | grep -E "^${name}=" | tail -n 1 || true)"
  value="$(
    printf '%s' "${line#*=}" |
      python3 -c 'import shlex, sys; value=sys.stdin.read(); print(shlex.split(value)[0] if value else "")'
  )"
  [[ -n "$value" ]] || {
    echo "Missing AZD environment value: $name" >&2
    exit 1
  }
  printf '%s' "$value"
}

require_file() {
  [[ -f "$1" ]] || {
    echo "Required deployment metadata is missing: $1" >&2
    exit 1
  }
}

active_revision() {
  local app_name="$1"
  local expected_image="$2"
  local revisions active
  revisions="$(
    az containerapp revision list \
      --subscription "$subscription_id" \
      --resource-group "$resource_group" \
      --name "$app_name" \
      --output json
  )"
  active="$(
    jq -c '
      [
        .[]
        | select((.active // .properties.active // false) == true)
        | {
            name: .name,
            image: (.template.containers[0].image // .properties.template.containers[0].image // ""),
            traffic_weight: (.trafficWeight // .properties.trafficWeight // 0),
            health_state: (.healthState // .properties.healthState // ""),
            running_state: (.runningState // .properties.runningState // "")
          }
      ]
    ' <<<"$revisions"
  )"
  [[ "$(jq 'length' <<<"$active")" -eq 1 ]] || {
    echo "Container App $app_name must have exactly one active revision." >&2
    exit 1
  }
  jq -e --arg image "$expected_image" '
    .[0].image == $image
    and .[0].traffic_weight == 100
    and .[0].running_state == "Running"
    and .[0].health_state == "Healthy"
  ' <<<"$active" >/dev/null || {
    echo "Container App $app_name active revision is not healthy on the expected image." >&2
    exit 1
  }
  jq -c '.[0]' <<<"$active"
}

container_env_value() {
  local container_app_json="$1"
  local name="$2"
  jq -r --arg name "$name" '
    [
      .properties.template.containers[0].env[]?
      | select(.name == $name)
      | if (.secretRef // "") != "" then "secretref:" + .secretRef else (.value // "") end
    ][0] // empty
  ' <<<"$container_app_json"
}

for command in az azd curl jq sha256sum; do
  require_bin "$command"
done
PYTHON="$ROOT_DIR/backend/.venv/bin/python"
[[ -x "$PYTHON" ]] || {
  echo "Backend virtual environment is required; run make ensure-backend-env." >&2
  exit 1
}

require_file "$BACKEND_METADATA_FILE"
require_file "$FRONTEND_METADATA_FILE"
require_file "$HOSTED_METADATA_FILE"
require_file "$RUNTIME_CONNECTION_METADATA_FILE"
"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"
AZD_ENV_VALUES="$(
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-values --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null
)"

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
location="$(required_env AZURE_LOCATION)"
backend_name="$(required_env BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(required_env FRONTEND_CONTAINER_APP_NAME)"
foundry_account="$(required_env FOUNDRY_ACCOUNT_NAME)"
foundry_project="$(required_env FOUNDRY_PROJECT_NAME)"
project_endpoint="$(required_env AZURE_AI_PROJECT_ENDPOINT)"
agent_name="$(required_env HOSTED_AGENT_NAME)"
runtime_database_url="$(required_env RUNTIME_DATABASE_URL)"
runtime_connection_name="$(required_env FOUNDRY_RUNTIME_CONNECTION_NAME)"

[[ "$subscription_id" == "7df95e88-701c-4693-af77-3159f83b558d" ]] || {
  echo "Verification requires the canonical public subscription." >&2
  exit 1
}
[[ "$resource_group" == "rg-langgraph-ora-foundry-public" ]] || {
  echo "Verification requires the canonical public resource group." >&2
  exit 1
}
[[ "${location,,}" == "eastus2" ]] || {
  echo "Verification requires the canonical eastus2 location." >&2
  exit 1
}

if [[ -f "$CONTEXT_FILE" ]]; then
  release_id="$(jq -r '.release_id // empty' "$CONTEXT_FILE")"
  release_started_at="$(jq -r '.started_at // empty' "$CONTEXT_FILE")"
else
  release_id="$(jq -r '.release_id // empty' "$BACKEND_METADATA_FILE")"
  release_started_at="$(jq -r '.release_started_at // empty' "$BACKEND_METADATA_FILE")"
fi
[[ -n "$release_id" && -n "$release_started_at" ]] || {
  echo "Release context is missing release_id or started_at." >&2
  exit 1
}

expected_backend_image="$(jq -r '.image // empty' "$BACKEND_METADATA_FILE")"
expected_frontend_image="$(jq -r '.image // empty' "$FRONTEND_METADATA_FILE")"
expected_hosted_image="$(jq -r '.image // empty' "$HOSTED_METADATA_FILE")"
expected_agent_version="$(jq -r '.version // empty' "$HOSTED_METADATA_FILE")"
expected_principal_id="$(jq -r '.principal_id // empty' "$HOSTED_METADATA_FILE")"
expected_runtime_connection_name="$(
  jq -r '.connection_name // empty' "$RUNTIME_CONNECTION_METADATA_FILE"
)"
for metadata_file in \
  "$BACKEND_METADATA_FILE" \
  "$FRONTEND_METADATA_FILE" \
  "$HOSTED_METADATA_FILE" \
  "$RUNTIME_CONNECTION_METADATA_FILE"; do
  [[ "$(jq -r '.release_id // empty' "$metadata_file")" == "$release_id" ]] || {
    echo "Deployment metadata spans multiple release windows: $metadata_file" >&2
    exit 1
  }
done
for image in "$expected_backend_image" "$expected_frontend_image" "$expected_hosted_image"; do
  [[ "$image" =~ @sha256:[0-9a-f]{64}$ ]] || {
    echo "Deployment metadata must contain immutable image digests." >&2
    exit 1
  }
done
[[ -n "$expected_agent_version" && -n "$expected_principal_id" ]] || {
  echo "Hosted-agent deployment metadata is incomplete." >&2
  exit 1
}
[[ "$runtime_connection_name" == "orderresolutionruntimesecrets" ]] &&
  [[ "$expected_runtime_connection_name" == "$runtime_connection_name" ]] &&
  [[ "$(jq -r '.runtime_connection_name // empty' "$HOSTED_METADATA_FILE")" == "$runtime_connection_name" ]] || {
  echo "Runtime connection metadata does not match the deterministic selected connection." >&2
  exit 1
}
[[ "$(required_env AGENT_ORDER_RESOLUTION_HOSTED_VERSION)" == "$expected_agent_version" ]] &&
  [[ "$(required_env AGENT_ORDER_RESOLUTION_HOSTED_IMAGE)" == "$expected_hosted_image" ]] &&
  [[ "$(required_env AGENT_ORDER_RESOLUTION_HOSTED_PRINCIPAL_ID)" == "$expected_principal_id" ]] || {
  echo "Selected AZD hosted-agent metadata does not match deployment metadata." >&2
  exit 1
}

az account set --subscription "$subscription_id"
verification_temp_dir="$ROOT_DIR/backend/.tmp/deployment-verify-${BASHPID}"
mkdir -p "$verification_temp_dir"
trap 'rm -rf "$verification_temp_dir"' EXIT
backend_json_file="$verification_temp_dir/backend.containerapp.json"
frontend_json_file="$verification_temp_dir/frontend.containerapp.json"
backend_revision_file="$verification_temp_dir/backend.revision.json"
frontend_revision_file="$verification_temp_dir/frontend.revision.json"
(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --output json >"$backend_json_file"
) &
backend_show_pid=$!
(
  az containerapp show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$frontend_name" \
    --output json >"$frontend_json_file"
) &
frontend_show_pid=$!
backend_show_status=0
frontend_show_status=0
wait "$backend_show_pid" || backend_show_status=$?
wait "$frontend_show_pid" || frontend_show_status=$?
if (( backend_show_status != 0 || frontend_show_status != 0 )); then
  echo "Unable to read both Container App resources." >&2
  exit 1
fi
backend_json="$(cat "$backend_json_file")"
frontend_json="$(cat "$frontend_json_file")"

backend_external="$(jq -r '.properties.configuration.ingress.external' <<<"$backend_json")"
frontend_external="$(jq -r '.properties.configuration.ingress.external' <<<"$frontend_json")"
backend_revision_mode="$(jq -r '.properties.configuration.activeRevisionsMode // empty' <<<"$backend_json")"
frontend_revision_mode="$(jq -r '.properties.configuration.activeRevisionsMode // empty' <<<"$frontend_json")"
[[ "$backend_external" == "false" && "$frontend_external" == "true" ]] &&
  [[ "${backend_revision_mode,,}" == "single" && "${frontend_revision_mode,,}" == "single" ]] || {
  echo "Expected internal backend and external frontend ingress." >&2
  exit 1
}

active_revision "$backend_name" "$expected_backend_image" >"$backend_revision_file" &
backend_revision_pid=$!
active_revision "$frontend_name" "$expected_frontend_image" >"$frontend_revision_file" &
frontend_revision_pid=$!
backend_revision_status=0
frontend_revision_status=0
wait "$backend_revision_pid" || backend_revision_status=$?
wait "$frontend_revision_pid" || frontend_revision_status=$?
if (( backend_revision_status != 0 || frontend_revision_status != 0 )); then
  echo "Unable to verify both active Container App revisions." >&2
  exit 1
fi
backend_revision="$(cat "$backend_revision_file")"
frontend_revision="$(cat "$frontend_revision_file")"
backend_latest_ready="$(jq -r '.properties.latestReadyRevisionName // empty' <<<"$backend_json")"
frontend_latest_ready="$(jq -r '.properties.latestReadyRevisionName // empty' <<<"$frontend_json")"
[[ "$(jq -r '.name' <<<"$backend_revision")" == "$backend_latest_ready" ]] || {
  echo "Backend active revision is not the latest ready revision." >&2
  exit 1
}
[[ "$(jq -r '.name' <<<"$frontend_revision")" == "$frontend_latest_ready" ]] || {
  echo "Frontend active revision is not the latest ready revision." >&2
  exit 1
}

backend_schema_managed_externally="$(
  container_env_value "$backend_json" DB_SCHEMA_MANAGED_EXTERNALLY
)"
[[ "$(container_env_value "$backend_json" DATABASE_URL)" == "secretref:database-url" ]] &&
  [[ "$(container_env_value "$backend_json" RUNTIME_DATABASE_URL)" == "secretref:database-url" ]] &&
  [[ "${backend_schema_managed_externally,,}" == "true" ]] || {
  echo "Backend runtime database or schema-management environment is incorrect." >&2
  exit 1
}
backend_database_url="$(
  az containerapp secret show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$backend_name" \
    --secret-name database-url \
    --query value \
    --output tsv
)"
[[ "$backend_database_url" == "$runtime_database_url" ]] || {
  echo "Backend runtime database secret does not match the selected runtime URL." >&2
  exit 1
}
expected_database_url_sha256="$(printf '%s' "$runtime_database_url" | sha256sum | cut -d' ' -f1)"
[[ "$(jq -r '.database_url_sha256 // empty' "$BACKEND_METADATA_FILE")" == "$expected_database_url_sha256" ]] || {
  echo "Backend deployment metadata does not match the selected runtime database URL." >&2
  exit 1
}

backend_fqdn="$(jq -r '.properties.configuration.ingress.fqdn // empty' <<<"$backend_json")"
frontend_fqdn="$(jq -r '.properties.configuration.ingress.fqdn // empty' <<<"$frontend_json")"
[[ -n "$backend_fqdn" && -n "$frontend_fqdn" ]] || {
  echo "Container App ingress FQDNs are missing." >&2
  exit 1
}
[[ "$(container_env_value "$frontend_json" API_BASE)" == "" ]] &&
  [[ "$(container_env_value "$frontend_json" NGINX_API_UPSTREAM)" == "https://${backend_fqdn}" ]] || {
  echo "Frontend is not configured for the same-origin backend proxy." >&2
  exit 1
}

frontend_url="https://${frontend_fqdn}"
curl --fail --silent --show-error --max-time 60 "$frontend_url/" >/dev/null
[[ "$(curl --fail --silent --show-error --max-time 60 "$frontend_url/health")" == "ok" ]] || {
  echo "Frontend health endpoint did not return ok." >&2
  exit 1
}
proxy_health="$(
  curl --fail --silent --show-error --max-time 60 "$frontend_url/api/health"
)"
jq -e '.status == "ok"' <<<"$proxy_health" >/dev/null || {
  echo "Same-origin backend health proxy failed." >&2
  exit 1
}

hosted_json=""
for attempt in $(seq 1 12); do
  if hosted_json="$(
    FOUNDRY_PROJECT_ENDPOINT="$project_endpoint" \
      FOUNDRY_HOSTED_AGENT_NAME="$agent_name" \
      FOUNDRY_HOSTED_AGENT_VERSION="$expected_agent_version" \
      FOUNDRY_EXPECTED_HOSTED_IMAGE="$expected_hosted_image" \
      FOUNDRY_RUNTIME_CONNECTION_NAME="$runtime_connection_name" \
      "$PYTHON" "$ROOT_DIR/scripts/foundry/verify_hosted_agent.py"
  )"; then
    break
  fi
  [[ "$attempt" -lt 12 ]] || exit 1
  echo "Hosted-agent activation has not propagated; retrying verification ($attempt/12)." >&2
  sleep 10
done
jq -e --arg principal "$expected_principal_id" '.principal_id == $principal' \
  <<<"$hosted_json" >/dev/null || {
  echo "Hosted-agent principal ID does not match deployment metadata." >&2
  exit 1
}
jq -e --arg connection "$runtime_connection_name" \
  '.runtime_connection_name == $connection
   and .checks.database_connection_placeholder_matches
   and .checks.runtime_database_connection_placeholder_matches' \
  <<<"$hosted_json" >/dev/null || {
  echo "Hosted-agent database variables do not use the expected connection placeholder." >&2
  exit 1
}

connection_url="https://management.azure.com/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/${foundry_account}/projects/${foundry_project}/connections/${runtime_connection_name}?api-version=2025-04-01-preview"
runtime_connection_json="$(
  az rest \
    --subscription "$subscription_id" \
    --method get \
    --url "$connection_url" \
    --query '{name:name,category:properties.category,auth_type:properties.authType}' \
    --output json
)"
jq -e \
  --arg name "$runtime_connection_name" \
  '.name == $name and .category == "CustomKeys" and .auth_type == "CustomKeys"' \
  <<<"$runtime_connection_json" >/dev/null || {
  echo "Foundry runtime secret connection is missing or misconfigured." >&2
  exit 1
}

foundry_scope="$(
  az cognitiveservices account show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$foundry_account" \
    --query id \
    --output tsv
)"
rbac_assignments="$(
  az role assignment list \
    --subscription "$subscription_id" \
    --assignee-object-id "$expected_principal_id" \
    --role "Cognitive Services OpenAI User" \
    --scope "$foundry_scope" \
    --fill-principal-name false \
    --output json
)"
jq -e --arg scope "${foundry_scope,,}" '
  any(.[]; ((.scope // "") | ascii_downcase) == $scope)
' <<<"$rbac_assignments" >/dev/null || {
  echo "Hosted-agent OpenAI User role is missing at the Foundry account scope." >&2
  exit 1
}

appinsights_evidence="${APPINSIGHTS_CONNECTION_EVIDENCE_FILE:-$RESULTS_DIR/appinsights-connection-evidence.json}"
FOUNDRY_RELEASE_ID="$release_id" \
  FOUNDRY_RELEASE_STARTED_AT="$release_started_at" \
  APPINSIGHTS_CONNECTION_EVIDENCE_FILE="$appinsights_evidence" \
  "$ROOT_DIR/scripts/foundry/verify_project_appinsights_connection.sh"

database_url_sha256="$expected_database_url_sha256"
mkdir -p "$(dirname "$EVIDENCE_FILE")"
jq -n \
  --arg release_id "$release_id" \
  --arg release_started_at "$release_started_at" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg subscription_id "$subscription_id" \
  --arg resource_group "$resource_group" \
  --arg location "$location" \
  --arg frontend_url "$frontend_url" \
  --arg database_url_sha256 "$database_url_sha256" \
  --arg runtime_connection_name "$runtime_connection_name" \
  --argjson backend_revision "$backend_revision" \
  --argjson frontend_revision "$frontend_revision" \
  --argjson hosted_agent "$hosted_json" \
  --slurpfile appinsights "$appinsights_evidence" \
  '{
    schema_version: 1,
    evidence_type: "deployment_verification",
    status: "passed",
    release_id: $release_id,
    release_started_at: $release_started_at,
    generated_at: $generated_at,
    target: {
      subscription_id: $subscription_id,
      resource_group: $resource_group,
      location: $location
    },
    container_apps: {
      backend: ($backend_revision + {external: false}),
      frontend: ($frontend_revision + {external: true})
    },
    endpoints: {
      frontend_url: $frontend_url,
      frontend_health: "passed",
      same_origin_backend_health_proxy: "passed"
    },
    hosted_agent: $hosted_agent,
    runtime_connection: {
      connection_name: $runtime_connection_name,
      category: "CustomKeys",
      auth_type: "CustomKeys",
      key_name: "database_url",
      hosted_placeholders_verified: true
    },
    database: {
      backend_runtime_database_url_matches: true,
      database_url_sha256: $database_url_sha256,
      schema_managed_externally: true
    },
    appinsights_connection: $appinsights[0]
  }' >"$EVIDENCE_FILE"

echo "Foundry deployment verification passed."
echo "Evidence written to ${EVIDENCE_FILE}."
