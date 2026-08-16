#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
EVIDENCE_FILE="${HOSTED_SMOKE_EVIDENCE_FILE:-$ROOT_DIR/backend/.foundry/results/hosted-smoke-evidence.json}"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
HOSTED_AGENT_NAME="${HOSTED_AGENT_NAME:-$(
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value HOSTED_AGENT_NAME --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
)}"
HOSTED_AGENT_NAME="${HOSTED_AGENT_NAME:-order-resolution-hosted}"

for command in azd jq; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required binary: $command" >&2
    exit 1
  }
done

extract_json_output() {
  local raw="${1:-}"
  local json_output
  json_output="$(
    printf '%s\n' "$raw" |
      sed -n "s/^\\[$HOSTED_AGENT_NAME\\][[:space:]]*//p" |
      tail -n 1
  )"
  if [[ -z "$json_output" ]]; then
    json_output="$(printf '%s\n' "$raw" | awk '
      found { print; next }
      /^\{/ {
        found = 1
        print
      }
    ')"
  fi
  printf '%s\n' "$json_output"
}

message="${SMOKE_MESSAGE:-Resolve delayed order ORD-1009}"
raw=""
rc=0
for attempt in $(seq 1 20); do
  set +e
  if [[ -n "${SMOKE_THREAD_ID:-}" ]]; then
    raw="$(
      cd "$FOUNDRY_DIR" &&
        AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
          azd ai agent invoke "$HOSTED_AGENT_NAME" "$message" \
          --protocol responses \
          --conversation-id "$SMOKE_THREAD_ID" \
          --no-prompt 2>&1
    )"
  else
    raw="$(
      cd "$FOUNDRY_DIR" &&
        AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
          azd ai agent invoke "$HOSTED_AGENT_NAME" "$message" \
          --protocol responses \
          --new-conversation \
          --new-session \
          --no-prompt 2>&1
    )"
  fi
  rc=$?
  set -e
  if [[ $rc -eq 0 ]] && ! grep -Eqi 'session_not_ready|424 Failed Dependency' <<<"$raw"; then
    break
  fi
  if grep -Eqi 'HTTP (404|409|429|5[0-9]{2})|session_not_ready|424 Failed Dependency' <<<"$raw"; then
    echo "Transient hosted smoke failure (${attempt}/20); retrying."
    sleep 15
    continue
  fi
  break
done

response="$(extract_json_output "$raw")"
if [[ $rc -ne 0 || -z "$response" ]]; then
  echo "Hosted smoke invocation failed." >&2
  printf '%s\n' "$raw" >&2
  exit 1
fi
jq -e '.status == "completed" or .status == "waiting_approval"' <<<"$response" >/dev/null
conversation_id="$(
  jq -r '[.. | objects | (.thread_id? // .conversation_id? // empty)]
    | map(select(type == "string" and length > 0))
    | .[0] // empty' <<<"$response"
)"
[[ -n "$conversation_id" ]] || {
  echo "Hosted smoke response did not include a conversation ID." >&2
  exit 1
}
response_status="$(jq -r '.status' <<<"$response")"
event_types="$(jq -c '(.events // []) | map(.type) | unique' <<<"$response")"

release_id="${FOUNDRY_RELEASE_ID:-manual-hosted-smoke}"
release_started_at="${FOUNDRY_RELEASE_STARTED_AT:-$STARTED_AT}"
mkdir -p "$(dirname "$EVIDENCE_FILE")"
jq -n \
  --arg release_id "$release_id" \
  --arg release_started_at "$release_started_at" \
  --arg started_at "$STARTED_AT" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg conversation_id "$conversation_id" \
  --arg response_status "$response_status" \
  --argjson event_types "$event_types" \
  '{
    schema_version: 1,
    evidence_type: "hosted_smoke",
    status: "passed",
    release_id: $release_id,
    release_started_at: $release_started_at,
    started_at: $started_at,
    generated_at: $generated_at,
    conversation_id: $conversation_id,
    response_status: $response_status,
    event_types: $event_types
  }' >"$EVIDENCE_FILE"

printf '%s\n' "$response"
echo "Hosted smoke passed for conversation ${conversation_id}."
echo "Evidence written to ${EVIDENCE_FILE}."
