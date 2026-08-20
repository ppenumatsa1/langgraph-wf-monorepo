#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

usage() {
  cat <<'EOF'
Usage: smoke-test.sh [options] [base_url] [thread_id]

Options:
  --mode <low-risk|high-risk>   Smoke mode (default: high-risk)
  --target <api|responses>      Invoke target (default: api)
  --base-url <url>              API base URL for --target api (default: http://localhost:8000)
  --thread-id <id>              Thread/conversation id seed
  --message <text>              Override default mode message
  --agent-name <name>           Hosted agent name for --target responses (default: order-resolution-hosted)
  -h, --help                    Show this help text
EOF
}

assert_json_field() {
  local json="$1"
  local expr="$2"
  echo "$json" | jq -e "$expr" >/dev/null || {
    echo "Assertion failed: $expr"
    echo "$json"
    exit 1
  }
}

MODE="high-risk"
TARGET="api"
BASE_URL="http://localhost:8000"
THREAD_ID="smoke-langgraph-foundry-hosted"
MESSAGE=""
AGENT_NAME="${HOSTED_AGENT_NAME:-order-resolution-hosted}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --target)
      TARGET="${2:-}"
      shift 2
      ;;
    --base-url)
      BASE_URL="${2:-}"
      shift 2
      ;;
    --thread-id)
      THREAD_ID="${2:-}"
      shift 2
      ;;
    --message)
      MESSAGE="${2:-}"
      shift 2
      ;;
    --agent-name)
      AGENT_NAME="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      if [[ "$BASE_URL" == "http://localhost:8000" ]]; then
        BASE_URL="$1"
      elif [[ "$THREAD_ID" == "smoke-langgraph-foundry-hosted" ]]; then
        THREAD_ID="$1"
      else
        echo "Unknown argument: $1"
        usage
        exit 1
      fi
      shift
      ;;
  esac
done

case "$MODE" in
  low-risk|high-risk) ;;
  *)
    echo "Invalid mode: $MODE (expected low-risk|high-risk)"
    exit 1
    ;;
esac

case "$TARGET" in
  api|responses) ;;
  *)
    echo "Invalid target: $TARGET (expected api|responses)"
    exit 1
    ;;
esac

if [[ -z "$MESSAGE" ]]; then
  if [[ "$MODE" == "low-risk" ]]; then
    MESSAGE="ORD-1001 delayed order"
  else
    MESSAGE="ORD-1009 delayed order"
  fi
fi

require_bin jq

payload_json=""
if [[ "$TARGET" == "api" ]]; then
  require_bin curl
  curl --fail --silent "$BASE_URL/health" >/dev/null
  request_payload="$(jq -nc --arg thread_id "$THREAD_ID" --arg message "$MESSAGE" '{thread_id: $thread_id, message: $message}')"
  payload_json="$(
    curl --fail --silent -X POST "$BASE_URL/api/chat/run" \
      -H 'Content-Type: application/json' \
      -d "$request_payload"
  )"
else
  require_bin azd
  raw="$(
    azd ai agent invoke "$AGENT_NAME" "$MESSAGE" \
      --protocol responses \
      --output raw \
      --no-prompt 2>&1
  )" || {
    echo "Smoke invoke failed for target=responses"
    echo "$raw"
    exit 1
  }
  payload_json="$(printf '%s\n' "$raw" | awk '
    found { print; next }
    /^\{/ {
      found = 1
      print
    }
  ')"
  if [[ -z "$payload_json" ]]; then
    echo "Could not extract JSON payload from responses output."
    echo "$raw"
    exit 1
  fi
  THREAD_ID="$(echo "$payload_json" | jq -r '[.. | objects | (.thread_id? // .conversation_id? // empty)] | map(select(type=="string" and length>0)) | .[0] // empty')"
  if [[ -z "$THREAD_ID" ]]; then
    echo "Could not determine thread_id from responses output."
    echo "$payload_json"
    exit 1
  fi
fi

if [[ "$MODE" == "low-risk" ]]; then
  assert_json_field "$payload_json" '(.events // []) | map(.type) | index("workflow.output") != null'
  assert_json_field "$payload_json" '(.events // []) | map(.type) | index("hitl.request") == null'
  if [[ "$TARGET" == "responses" ]]; then
    assert_json_field "$payload_json" '.status == "completed"'
  fi
  echo "foundry-hosted smoke test passed (low-risk completion path verified)"
else
  assert_json_field "$payload_json" '(.events // []) | map(.type) | index("checkpoint.created") != null'
  assert_json_field "$payload_json" '(.events // []) | map(.type) | index("hitl.request") != null'
  if [[ "$TARGET" == "responses" ]]; then
    assert_json_field "$payload_json" '.status == "waiting_approval"'
  fi
  echo "foundry-hosted smoke test passed (high-risk HITL path verified)"
fi

echo "smoke.thread_id=$THREAD_ID"
