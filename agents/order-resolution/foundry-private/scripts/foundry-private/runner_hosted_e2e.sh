#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

[[ "$1" == "hosted_e2e" ]] || private_die "private E2E stage mismatch"
for command in jq python3 tee; do
  private_require_command "$command"
done
private_require_target

agent_name="$(private_required_env_value HOSTED_AGENT_NAME)"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
release_id="$(private_release_id)"
evidence_file="$PRIVATE_ROOT_DIR/.artifacts/private-runner-hosted-e2e-${release_id}.json"
mkdir -p "$(dirname "$evidence_file")"

extract_json() {
  python3 "$SCRIPT_DIR/extract_azd_agent_json.py"
}

invoke_responses() {
  local message="$1"
  local conversation_id="${2:-}"
  local checkpoint_id="${3:-}"
  local raw json attempt
  local -a args

  args=(
    ai agent invoke "$agent_name" "$message"
    --protocol responses
    --no-prompt
  )
  if [[ -n "$conversation_id" ]]; then
    args+=(--conversation-id "$conversation_id")
  else
    args+=(--new-conversation --new-session)
  fi
  if [[ -n "$checkpoint_id" ]]; then
    args+=(
      --client-header "x-client-decision: approve"
      --client-header "x-client-checkpoint-id: $checkpoint_id"
    )
  fi

  for attempt in $(seq 1 12); do
    if raw="$(cd "$PRIVATE_AZD_DIR" && private_azd "${args[@]}" 2>&1)"; then
      json="$(printf '%s\n' "$raw" | extract_json)"
      [[ -n "$json" ]] ||
        private_die "private hosted E2E invocation returned no JSON response"
      jq -e 'type == "object"' <<<"$json" >/dev/null ||
        private_die "private hosted E2E invocation returned malformed JSON"
      printf '%s\n' "$json"
      return
    fi
    if grep -Eqi 'HTTP (404|409|429|5[0-9]{2})|internal server error|session_not_ready' <<<"$raw"; then
      sleep 15
      continue
    fi
    private_die "private hosted E2E invocation failed with a non-retryable response"
  done
  private_die "private hosted E2E invocation exhausted its bounded retry budget"
}

conversation_id() {
  jq -r '[.. | objects | (.thread_id? // .conversation_id? // empty)] | map(select(type == "string" and length > 0)) | .[0] // empty'
}

checkpoint_id() {
  jq -r '(.pending_approvals // [])[0].checkpoint_id // empty'
}

assert_event() {
  local response="$1"
  local event_type="$2"
  jq -e --arg event_type "$event_type" \
    '(.events // []) | map(.type) | index($event_type) != null' \
    <<<"$response" >/dev/null ||
    private_die "private hosted E2E response omitted required event: $event_type"
}

low_risk="$(invoke_responses "Resolve delayed order ORD-1001")"
jq -e '.status == "completed"' <<<"$low_risk" >/dev/null ||
  private_die "low-risk private hosted conversation did not complete"
assert_event "$low_risk" tool.call
assert_event "$low_risk" workflow.output
low_risk_id="$(conversation_id <<<"$low_risk")"
[[ -n "$low_risk_id" ]] || private_die "low-risk private hosted conversation has no ID"

high_risk_start="$(invoke_responses "Resolve delayed order ORD-1009")"
jq -e '.status == "waiting_approval"' <<<"$high_risk_start" >/dev/null ||
  private_die "high-risk private hosted conversation did not require approval"
assert_event "$high_risk_start" hitl.request
high_risk_id="$(conversation_id <<<"$high_risk_start")"
high_risk_checkpoint="$(checkpoint_id <<<"$high_risk_start")"
[[ -n "$high_risk_id" && -n "$high_risk_checkpoint" ]] ||
  private_die "high-risk private hosted conversation is missing HITL state"
high_risk_resume="$(invoke_responses "Approve" "$high_risk_id" "$high_risk_checkpoint")"
jq -e '.status == "completed"' <<<"$high_risk_resume" >/dev/null ||
  private_die "high-risk private hosted approval did not complete"
assert_event "$high_risk_resume" hitl.response
assert_event "$high_risk_resume" workflow.output

damaged_start="$(invoke_responses "Order ORD-1001 arrived damaged and broken.")"
jq -e '.status == "waiting_approval"' <<<"$damaged_start" >/dev/null ||
  private_die "damaged-item private hosted conversation did not require approval"
assert_event "$damaged_start" hitl.request
damaged_id="$(conversation_id <<<"$damaged_start")"
damaged_checkpoint="$(checkpoint_id <<<"$damaged_start")"
[[ -n "$damaged_id" && -n "$damaged_checkpoint" ]] ||
  private_die "damaged-item private hosted conversation is missing HITL state"
damaged_resume="$(invoke_responses "Approve" "$damaged_id" "$damaged_checkpoint")"
jq -e '.status == "completed"' <<<"$damaged_resume" >/dev/null ||
  private_die "damaged-item private hosted approval did not complete"
assert_event "$damaged_resume" hitl.response
assert_event "$damaged_resume" workflow.output

jq -n \
  --arg release_id "$release_id" \
  --arg started_at "$started_at" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg low_risk "$low_risk_id" \
  --arg high_risk "$high_risk_id" \
  --arg damaged "$damaged_id" \
  '{
    release_id: $release_id,
    started_at: $started_at,
    generated_at: $generated_at,
    conversation_ids: [$low_risk, $high_risk, $damaged],
    scenarios: [
      {name: "low_risk_no_hitl", order_id: "ORD-1001", conversation_id: $low_risk, expected_hitl: false, terminal_status: "completed"},
      {name: "high_risk_hitl_approval_resume", order_id: "ORD-1009", conversation_id: $high_risk, expected_hitl: true, decision: "approve", terminal_status: "completed"},
      {name: "damaged_item_hitl_approval_resume", order_id: "ORD-1001", conversation_id: $damaged, expected_hitl: true, decision: "approve", terminal_status: "completed"}
    ],
    low_risk_thread_id: $low_risk,
    approved_thread_id: $high_risk,
    damaged_item_thread_id: $damaged
  }' | tee "$evidence_file"
