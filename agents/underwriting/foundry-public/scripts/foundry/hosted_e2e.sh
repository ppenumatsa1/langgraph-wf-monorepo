#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

assert_json_field() {
  local json="$1"
  local expr="$2"
  printf '%s\n' "$json" | jq -e "$expr" >/dev/null || {
    echo "Assertion failed: $expr" >&2
    printf '%s\n' "$json" >&2
    exit 1
  }
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -n "${RELEASE_ID:-}" ]]; then
  . "$ROOT_DIR/scripts/foundry/release_paths.sh"
  release_paths_configure "$ROOT_DIR"
fi
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
EVIDENCE_FILE="${HOSTED_E2E_EVIDENCE_FILE:-$ROOT_DIR/backend/.foundry/results/hosted-e2e-evidence.json}"

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

api_post_json() {
  local url="$1"
  local payload="$2"
  curl --fail --silent --show-error --max-time 300 \
    -X POST "$url" \
    -H 'content-type: application/json' \
    -d "$payload"
}

api_get_json() {
  local url="$1"
  curl --fail --silent --show-error --max-time 60 "$url"
}

build_start_payload() {
  local workflow_run_id="$1"
  local application_id="$2"
  local fail_risk_once="$3"
  local crash_after_executor="$4"
  jq -nc \
    --arg workflow_run_id "$workflow_run_id" \
    --arg application_id "$application_id" \
    --arg applicant_name "Ada Lovelace" \
    --arg crash_after_executor "$crash_after_executor" \
    --argjson fail_risk_once "$fail_risk_once" \
    '{
      workflow_run_id: $workflow_run_id,
      application: {
        application_id: $application_id,
        applicant_name: $applicant_name,
        age: 38,
        income: 145000,
        requested_coverage: 500000,
        health_disclosures: "none",
        driving_history: "clean",
        credit_score: 760
      },
      fail_risk_once: $fail_risk_once,
      fail_credit_randomly: false,
      crash_after_executor: (if $crash_after_executor == "" then null else $crash_after_executor end)
    }'
}

write_evidence() {
  local playwright_status="$1"
  mkdir -p "$(dirname "$EVIDENCE_FILE")"
  jq -n \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg started_at "$started_at" \
    --arg frontend_url "$frontend_url" \
    --arg api_base_url "$frontend_url" \
    --arg resource_group "$resource_group" \
    --arg backend_name "$backend_name" \
    --arg frontend_name "$frontend_name" \
    --arg happy_run_id "$happy_run_id" \
    --arg retry_run_id "$retry_run_id" \
    --arg recovered_run_id "$recovered_run_id" \
    --arg happy_decision "$happy_decision" \
    --arg retry_decision "$retry_decision" \
    --arg recovered_decision "$recovered_decision" \
    --arg playwright_status "$playwright_status" \
    '{
      generated_at: $generated_at,
      started_at: $started_at,
      frontend_url: $frontend_url,
      api_base_url: $api_base_url,
      backend_ingress_external: false,
      resource_group: $resource_group,
      backend_container_app: $backend_name,
      frontend_container_app: $frontend_name,
      workflow_run_ids: [$happy_run_id, $retry_run_id, $recovered_run_id],
      happy_run_id: $happy_run_id,
      retry_run_id: $retry_run_id,
      recovered_run_id: $recovered_run_id,
      happy_decision: $happy_decision,
      retry_decision: $retry_decision,
      recovered_decision: $recovered_decision,
      playwright_status: $playwright_status
    }' >"$EVIDENCE_FILE"
}

require_bin az
require_bin azd
require_bin curl
require_bin jq
require_bin make

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"

resource_group="$(required_env AZURE_RESOURCE_GROUP)"
subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
backend_name="$(required_env BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(required_env FRONTEND_CONTAINER_APP_NAME)"
az account set --subscription "$subscription_id" >/dev/null
backend_fqdn="${BACKEND_FQDN:-$(az containerapp show --subscription "$subscription_id" --resource-group "$resource_group" --name "$backend_name" --query 'properties.configuration.ingress.fqdn' --output tsv)}"
frontend_fqdn="${FRONTEND_FQDN:-$(az containerapp show --subscription "$subscription_id" --resource-group "$resource_group" --name "$frontend_name" --query 'properties.configuration.ingress.fqdn' --output tsv)}"
frontend_url="${PLAYWRIGHT_BASE_URL:-${WEB_URL:-https://${frontend_fqdn}}}"
api_base_url="$frontend_url"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
run_nonce="$(date -u +%Y%m%d%H%M%S)-$$"
happy_run_id="run-hosted-happy-${run_nonce}"
retry_run_id="run-hosted-retry-${run_nonce}"
recovered_run_id="run-hosted-recover-${run_nonce}"
happy_decision=""
retry_decision=""
recovered_decision=""

curl --fail --silent --show-error --max-time 60 "$frontend_url" >/dev/null
api_get_json "$frontend_url/backend-health" >/dev/null
if curl --fail --silent --show-error --max-time 10 "https://${backend_fqdn}/health" >/dev/null 2>&1; then
  echo "Hosted E2E requires the backend ingress to be internal." >&2
  exit 1
fi

happy_response="$(
  api_post_json \
    "$api_base_url/api/v1/underwriting/runs" \
    "$(build_start_payload "$happy_run_id" "app-hosted-happy-${run_nonce}" false "")"
)"
assert_json_field "$happy_response" '.status == "COMPLETED"'
assert_json_field "$happy_response" '.outputs | length > 0'
happy_decision="$(printf '%s\n' "$happy_response" | jq -r '.outputs[0].decision // empty')"
[[ -n "$happy_decision" ]] || {
  echo "Hosted happy-path response did not contain a decision." >&2
  printf '%s\n' "$happy_response" >&2
  exit 1
}

happy_events="$(api_get_json "$api_base_url/api/v1/underwriting/runs/$happy_run_id/events")"
assert_json_field "$happy_events" 'length > 0'
assert_json_field "$happy_events" 'map(.created_at) == (map(.created_at) | sort)'
assert_json_field "$happy_events" 'map(select(.event_type == "fan_in_result_received")) | length == 4'

retry_response="$(
  api_post_json \
    "$api_base_url/api/v1/underwriting/runs" \
    "$(build_start_payload "$retry_run_id" "app-hosted-retry-${run_nonce}" true "")"
)"
assert_json_field "$retry_response" '.status == "COMPLETED"'
retry_decision="$(printf '%s\n' "$retry_response" | jq -r '.outputs[0].decision // empty')"
[[ -n "$retry_decision" ]] || {
  echo "Hosted retry response did not contain a decision." >&2
  exit 1
}
retry_events="$(api_get_json "$api_base_url/api/v1/underwriting/runs/$retry_run_id/events")"
assert_json_field "$retry_events" 'map(.event_type) | index("retry_backoff") != null'
assert_json_field "$retry_events" 'map(select(.event_type == "fan_in_result_received")) | length == 4'

crash_response="$(
  api_post_json \
    "$api_base_url/api/v1/underwriting/runs" \
    "$(build_start_payload "$recovered_run_id" "app-hosted-recover-${run_nonce}" false "medical_check")"
)"
assert_json_field "$crash_response" '.status == "CRASHED"'

crash_checkpoints="$(api_get_json "$api_base_url/api/v1/underwriting/runs/$recovered_run_id/checkpoints")"
assert_json_field "$crash_checkpoints" 'length > 0'

resume_response="$(api_post_json "$api_base_url/api/v1/underwriting/runs/$recovered_run_id/resume" '{}')"
assert_json_field "$resume_response" '.status == "COMPLETED"'
assert_json_field "$resume_response" '.outputs | length > 0'
recovered_decision="$(printf '%s\n' "$resume_response" | jq -r '.outputs[0].decision // empty')"
[[ -n "$recovered_decision" ]] || {
  echo "Hosted resume response did not contain a decision." >&2
  printf '%s\n' "$resume_response" >&2
  exit 1
}

recovered_events="$(api_get_json "$api_base_url/api/v1/underwriting/runs/$recovered_run_id/events")"
assert_json_field "$recovered_events" 'length > 0'
assert_json_field "$recovered_events" 'map(.created_at) == (map(.created_at) | sort)'
assert_json_field "$recovered_events" 'map(select(.event_type == "fan_in_result_received")) | length == 4'
assert_json_field "$recovered_events" 'map(.event_type) | index("idempotency_skip") != null'

recovered_run="$(api_get_json "$api_base_url/api/v1/underwriting/runs/$recovered_run_id")"
assert_json_field "$recovered_run" '.status == "COMPLETED"'

write_evidence pending
PLAYWRIGHT_BASE_URL="$frontend_url" make -C "$ROOT_DIR" test-e2e
write_evidence passed

echo "Hosted underwriting E2E passed for ${happy_run_id}, ${retry_run_id}, and ${recovered_run_id}."
echo "Evidence written to ${EVIDENCE_FILE}."
