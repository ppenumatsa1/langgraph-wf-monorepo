#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

[[ "$1" == "verify_runtime" ]] || private_die "runtime verification stage mismatch"
for command in az curl jq; do
  private_require_command "$command"
done
private_require_target

subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(private_azd_value AZURE_RESOURCE_GROUP)"
backend_name="$(private_required_env_value BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(private_required_env_value FRONTEND_CONTAINER_APP_NAME)"
backend_image="$(private_required_env_value PRIVATE_BACKEND_IMAGE)"
frontend_image="$(private_required_env_value PRIVATE_FRONTEND_IMAGE)"
hosted_image="$(private_required_env_value PRIVATE_HOSTED_IMAGE)"
hosted_version="$(private_required_env_value AGENT_ORDER_RESOLUTION_PRIVATE_HOSTED_VERSION)"
hosted_principal_id="$(private_required_env_value AGENT_ORDER_RESOLUTION_PRIVATE_HOSTED_PRINCIPAL_ID)"
agent_name="$(private_required_env_value HOSTED_AGENT_NAME)"
project_endpoint="$(private_required_env_value AZURE_AI_PROJECT_ENDPOINT)"
runtime_connection="$(private_required_env_value FOUNDRY_RUNTIME_CONNECTION_NAME)"
python="$PRIVATE_ROOT_DIR/backend/.venv/bin/python"
hosted_verifier="$SCRIPT_DIR/verify_hosted_agent.py"
[[ -x "$python" ]] || private_die "private runner requires backend/.venv for hosted verification"
private_require_file "$hosted_verifier"

backend_json="$(az containerapp show --subscription "$subscription_id" --resource-group "$resource_group" --name "$backend_name" --output json)"
frontend_json="$(az containerapp show --subscription "$subscription_id" --resource-group "$resource_group" --name "$frontend_name" --output json)"
for item in "$backend_json" "$frontend_json"; do
  [[ "$(jq -r '.properties.configuration.activeRevisionsMode // empty' <<<"$item")" == "Single" ]] ||
    private_die "private Container Apps must use single-revision deployment"
done
[[ "$(jq -r '.properties.configuration.ingress.external // empty' <<<"$backend_json")" == "false" ]] ||
  private_die "private backend ingress must remain internal"
[[ "$(jq -r '.properties.configuration.ingress.external // empty' <<<"$frontend_json")" == "true" ]] ||
  private_die "private frontend must be the lane's only external ingress"
[[ "$(jq -r '.properties.template.containers[0].image // empty' <<<"$backend_json")" == "$backend_image" ]] ||
  private_die "backend does not use the expected immutable private image"
[[ "$(jq -r '.properties.template.containers[0].image // empty' <<<"$frontend_json")" == "$frontend_image" ]] ||
  private_die "frontend does not use the expected immutable private image"
jq -e '
  [
    .properties.template.containers[0].env[]?
    | select(.name == "DATABASE_URL" or .name == "RUNTIME_DATABASE_URL")
  ]
  | length == 2
  and all(.[]; .secretRef == "database-url" and (.value // "") == "")
' <<<"$backend_json" >/dev/null ||
  private_die "private backend database variables must use the runtime secret reference"
jq -e '
  [
    .properties.template.containers[0].env[]?
    | select(.name == "APPLICATIONINSIGHTS_CONNECTION_STRING")
  ]
  | length == 1
  and .[0].secretRef == "appinsights-connection-string"
' <<<"$backend_json" >/dev/null ||
  private_die "private backend must retain its Application Insights secret reference"
jq -e '
  [
    .properties.template.containers[0].env[]?
    | select(.name == "OTEL_RECORD_CONTENT" or .name == "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT")
  ]
  | length == 2
  and all(.[]; (.value // "") == "false")
' <<<"$backend_json" >/dev/null ||
  private_die "private backend telemetry content must remain redacted"

frontend_fqdn="$(jq -r '.properties.configuration.ingress.fqdn // empty' <<<"$frontend_json")"
[[ -n "$frontend_fqdn" ]] || private_die "private frontend FQDN is missing"
[[ "$(curl --fail --silent --show-error --max-time 60 "https://${frontend_fqdn}/health")" == "ok" ]] ||
  private_die "private frontend health check failed from the runner"
curl --fail --silent --show-error --max-time 60 "https://${frontend_fqdn}/api/health" |
  jq -e '.status == "ok"' >/dev/null ||
  private_die "private same-origin backend health check failed from the runner"

hosted_json=""
for attempt in $(seq 1 12); do
  if hosted_json="$(
    FOUNDRY_PROJECT_ENDPOINT="$project_endpoint" \
    FOUNDRY_HOSTED_AGENT_NAME="$agent_name" \
    FOUNDRY_HOSTED_AGENT_VERSION="$hosted_version" \
    FOUNDRY_EXPECTED_HOSTED_IMAGE="$hosted_image" \
    FOUNDRY_RUNTIME_CONNECTION_NAME="$runtime_connection" \
      "$python" "$hosted_verifier"
  )"; then
    break
  fi
  [[ "$attempt" -lt 12 ]] ||
    private_die "private hosted agent did not converge to its immutable active version"
  sleep 10
done
jq -e --arg principal "$hosted_principal_id" '.principal_id == $principal' \
  <<<"$hosted_json" >/dev/null ||
  private_die "private hosted agent principal does not match the immutable deployment"

jq -n \
  --arg backend "$backend_name" \
  --arg frontend "$frontend_name" \
  --arg hosted_version "$hosted_version" \
  --arg hosted_principal_id "$hosted_principal_id" \
  '{backend:$backend,frontend:$frontend,hosted_version:$hosted_version,hosted_principal_id:$hosted_principal_id,backend_external_ingress:false,frontend_external_ingress:true,same_origin_private_health:true}'
