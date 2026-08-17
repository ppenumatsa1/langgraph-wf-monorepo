#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

usage() {
  cat <<'USAGE'
Usage: smoke-test.sh [--mode <happy|retry|crash-resume>]

Runs a direct Responses smoke against the deployed underwriting-hosted agent and
writes trace-evaluation evidence to backend/.foundry/results/hosted-smoke-evidence.json.
USAGE
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

extract_json_output() {
  python3 - "$1" <<'PY'
import json
import re
import sys

raw = sys.argv[1]
decoder = json.JSONDecoder()
values = []
offset = 0

while match := re.search(r"[\[{]", raw[offset:]):
    start = offset + match.start()
    try:
        value, end = decoder.raw_decode(raw, start)
    except json.JSONDecodeError:
        offset = start + 1
        continue
    values.append(value)
    offset = end

if values:
    print(json.dumps(values))
PY
}

extract_agent_result() {
  python3 - "$1" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1])

def find_result(value):
    if isinstance(value, dict):
        if "workflow_run_id" in value and "status" in value:
            return value
        for nested in value.values():
            found = find_result(nested)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = find_result(nested)
            if found is not None:
                return found
    elif isinstance(value, str) and value.lstrip().startswith("{"):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return find_result(parsed)
    return None

print(json.dumps(find_result(payload) or {}))
PY
}

extract_conversation_id() {
  local json_payload="$1"
  local raw_payload="$2"
  local conversation_id
  conversation_id="$(printf '%s\n' "$json_payload" | jq -r '[.. | objects | (.thread_id? // .conversation_id? // empty)] | map(select(type == "string" and length > 0)) | .[0] // empty')"
  if [[ -z "$conversation_id" ]]; then
    conversation_id="$(printf '%s\n' "$raw_payload" | grep -Eo 'conv_[A-Za-z0-9_-]+' | head -n 1 || true)"
  fi
  printf '%s' "$conversation_id"
}

extract_trace_id() {
  local json_payload="$1"
  printf '%s\n' "$json_payload" | jq -r '[.. | objects | (.trace_id? // .traceId? // empty)] | map(select(type == "string" and length > 0)) | .[0] // empty'
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
      protocol: "underwriting-hosted-workflow/v1",
      workflow_run_id: $workflow_run_id,
      action: "start",
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
      options: {
        fail_risk_once: $fail_risk_once,
        fail_credit_randomly: false,
        crash_after_executor: (if $crash_after_executor == "" then null else $crash_after_executor end)
      }
    }'
}

build_resume_payload() {
  local workflow_run_id="$1"
  jq -nc \
    --arg workflow_run_id "$workflow_run_id" \
    '{
      protocol: "underwriting-hosted-workflow/v1",
      workflow_run_id: $workflow_run_id,
      action: "resume"
    }'
}

invoke_responses() {
  local agent_name="$1"
  local payload_json="$2"
  local conversation_id="${3:-}"
  local mode="${4:-reuse}"
  local raw rc max_attempts retry_seconds
  max_attempts="${FOUNDRY_SMOKE_MAX_ATTEMPTS:-20}"
  retry_seconds="${FOUNDRY_SMOKE_RETRY_SECONDS:-15}"
  for attempt in $(seq 1 "$max_attempts"); do
    set +e
    if [[ -n "$conversation_id" ]]; then
      raw="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent invoke "$agent_name" "$payload_json" --protocol responses --conversation-id "$conversation_id" --output raw --no-prompt 2>&1)"
    elif [[ "$mode" == "new" ]]; then
      raw="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent invoke "$agent_name" "$payload_json" --protocol responses --new-conversation --new-session --output raw --no-prompt 2>&1)"
    else
      raw="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd ai agent invoke "$agent_name" "$payload_json" --protocol responses --output raw --no-prompt 2>&1)"
    fi
    rc=$?
    set -e
    if [[ $rc -eq 0 ]] && printf '%s\n' "$raw" | grep -Eqi 'session_not_ready|424 Failed Dependency|"code"[[:space:]]*:[[:space:]]*"session_not_ready"'; then
      rc=1
    fi
    if [[ $rc -eq 0 ]]; then
      break
    fi
    if printf '%s\n' "$raw" | grep -Eqi 'HTTP (404|409|429|5[0-9]{2})|context deadline exceeded|session_not_ready'; then
      echo "Transient invoke failure (attempt $attempt/$max_attempts); retrying..."
      sleep "$retry_seconds"
      continue
    fi
    echo "Smoke invoke failed:" >&2
    printf '%s\n' "$raw" >&2
    exit "$rc"
  done
  if [[ $rc -eq 0 ]]; then
    printf '%s\n' "$raw"
    return
  fi
  echo "Smoke invoke did not become ready after $max_attempts attempts." >&2
  printf '%s\n' "$raw" >&2
  exit "${rc:-1}"
}

MODE="${SMOKE_MODE:-happy}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

case "$MODE" in
  happy|retry|crash-resume) ;;
  *)
    echo "Invalid mode: $MODE (expected happy|retry|crash-resume)" >&2
    exit 1
    ;;
esac

require_bin azd
require_bin jq
require_bin python3

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
if [[ -n "${RELEASE_ID:-}" ]]; then
  . "$ROOT_DIR/scripts/foundry/release_paths.sh"
  release_paths_configure "$ROOT_DIR"
fi
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
EVIDENCE_FILE="${FOUNDRY_SMOKE_EVIDENCE_FILE:-$ROOT_DIR/backend/.foundry/results/hosted-smoke-evidence.json}"

"$ROOT_DIR/scripts/foundry/ensure_foundry_azd_defaults.sh"
cd "$FOUNDRY_DIR"
agent_name="${HOSTED_AGENT_NAME:-$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd env get-value HOSTED_AGENT_NAME --no-prompt 2>/dev/null || true)}"
agent_name="${agent_name:-underwriting-hosted}"
run_nonce="$(date -u +%Y%m%d%H%M%S)-$$"
workflow_run_id="run-smoke-${run_nonce}"
application_id="app-smoke-${run_nonce}"
trace_id=""
decision=""
conversation_id=""

if [[ "$MODE" == "crash-resume" ]]; then
  start_raw="$(invoke_responses "$agent_name" "$(build_start_payload "$workflow_run_id" "$application_id" true "medical_check")" "" new)"
  start_json="$(extract_json_output "$start_raw")"
  [[ -n "$start_json" ]] || {
    echo "Unable to extract JSON payload from smoke invoke output." >&2
    printf '%s\n' "$start_raw" >&2
    exit 1
  }
  agent_start_result="$(extract_agent_result "$start_json")"
  assert_json_field "$agent_start_result" '.status == "CRASHED"'
  workflow_run_id="$(printf '%s\n' "$agent_start_result" | jq -r '.workflow_run_id // empty')"
  conversation_id="$(extract_conversation_id "$start_json" "$start_raw")"
  [[ -n "$conversation_id" ]] || {
    echo "Unable to determine the hosted conversation ID for smoke evidence." >&2
    printf '%s\n' "$start_raw" >&2
    exit 1
  }
  trace_id="$(extract_trace_id "$start_json")"

  resume_raw="$(invoke_responses "$agent_name" "$(build_resume_payload "$workflow_run_id")" "$conversation_id")"
  resume_json="$(extract_json_output "$resume_raw")"
  [[ -n "$resume_json" ]] || {
    echo "Unable to extract JSON payload from resume smoke output." >&2
    printf '%s\n' "$resume_raw" >&2
    exit 1
  }
  agent_resume_result="$(extract_agent_result "$resume_json")"
  assert_json_field "$agent_resume_result" '.status == "COMPLETED"'
  assert_json_field "$agent_resume_result" '.outputs | length > 0'
  decision="$(printf '%s\n' "$agent_resume_result" | jq -r '.outputs[0].decision // empty')"
else
  fail_risk_once=false
  if [[ "$MODE" == "retry" ]]; then
    fail_risk_once=true
  fi
  smoke_raw="$(invoke_responses "$agent_name" "$(build_start_payload "$workflow_run_id" "$application_id" "$fail_risk_once" "")" "" new)"
  smoke_json="$(extract_json_output "$smoke_raw")"
  [[ -n "$smoke_json" ]] || {
    echo "Unable to extract JSON payload from smoke invoke output." >&2
    printf '%s\n' "$smoke_raw" >&2
    exit 1
  }
  agent_smoke_result="$(extract_agent_result "$smoke_json")"
  assert_json_field "$agent_smoke_result" '.status == "COMPLETED"'
  assert_json_field "$agent_smoke_result" '.outputs | length > 0'
  workflow_run_id="$(printf '%s\n' "$agent_smoke_result" | jq -r '.workflow_run_id // empty')"
  decision="$(printf '%s\n' "$agent_smoke_result" | jq -r '.outputs[0].decision // empty')"
  conversation_id="$(extract_conversation_id "$smoke_json" "$smoke_raw")"
  [[ -n "$conversation_id" ]] || {
    echo "Unable to determine the hosted conversation ID for smoke evidence." >&2
    printf '%s\n' "$smoke_raw" >&2
    exit 1
  }
  trace_id="$(extract_trace_id "$smoke_json")"
fi

mkdir -p "$(dirname "$EVIDENCE_FILE")"
if [[ -n "$trace_id" ]]; then
  jq -n \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg mode "$MODE" \
    --arg workflow_run_id "$workflow_run_id" \
    --arg decision "$decision" \
    --arg trace_id "$trace_id" \
    --arg conversation_id "$conversation_id" \
    '{
      generated_at: $generated_at,
      mode: $mode,
      conversation_ids: [$conversation_id],
      trace_id: $trace_id,
      workflow_run_id: $workflow_run_id,
      decision: $decision
    }' >"$EVIDENCE_FILE"
else
  jq -n \
    --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg mode "$MODE" \
    --arg workflow_run_id "$workflow_run_id" \
    --arg decision "$decision" \
    --arg conversation_id "$conversation_id" \
    '{
      generated_at: $generated_at,
      mode: $mode,
      conversation_ids: [$conversation_id],
      workflow_run_id: $workflow_run_id,
      decision: $decision
    }' >"$EVIDENCE_FILE"
fi

echo "Hosted underwriting smoke passed (${MODE}) for workflow_run_id=${workflow_run_id}."
echo "Evidence written to ${EVIDENCE_FILE}."
