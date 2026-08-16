#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

"$ROOT_DIR/scripts/foundry/bootstrap_azd_env.sh"

get_env() {
  local value
  if ! value="$(
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
      azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null
  )"; then
    return 0
  fi
  printf '%s' "$value"
}

set_if_missing() {
  local name="$1"
  local value="$2"
  if [[ -z "$(get_env "$name")" && -n "$value" ]]; then
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
      azd env set "$name" "$value" --cwd "$FOUNDRY_DIR" --no-prompt >/dev/null
  fi
}

project_endpoint="$(get_env AZURE_AI_PROJECT_ENDPOINT)"
hosted_agent_name="$(get_env HOSTED_AGENT_NAME)"
set_if_missing FOUNDRY_PROJECTS_ENDPOINT "$project_endpoint"
set_if_missing FOUNDRY_PROJECT_ENDPOINT "$project_endpoint"
set_if_missing FOUNDRY_HOSTED_AGENT_NAME "$hosted_agent_name"
set_if_missing FOUNDRY_RUNTIME_CONNECTION_NAME orderresolutionruntimesecrets
set_if_missing FOUNDRY_RESPONSES_ENDPOINT "${project_endpoint}/agents/${hosted_agent_name}/endpoint/protocols/openai/responses?api-version=v1"
set_if_missing APPINSIGHTS_CONNECTION_STRING "$(get_env APPLICATIONINSIGHTS_CONNECTION_STRING)"
set_if_missing APP_ENV aca-public
set_if_missing STORE_PROVIDER postgres
set_if_missing RUNTIME_TARGET responses_wrapper
set_if_missing DB_SCHEMA_MANAGED_EXTERNALLY true
set_if_missing ENABLE_TELEMETRY true
set_if_missing ENABLE_INSTRUMENTATION true
set_if_missing OTEL_SERVICE_NAME langgraph-order-resolution-aca-backend
set_if_missing OTEL_SERVICE_NAMESPACE langgraph-order-resolution
set_if_missing OTEL_RECORD_CONTENT false
set_if_missing FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT true
set_if_missing FOUNDRY_HOSTED_OTEL_SERVICE_NAME langgraph-order-resolution-hosted
set_if_missing FOUNDRY_OTEL_SERVICE_NAMESPACE langgraph-order-resolution
