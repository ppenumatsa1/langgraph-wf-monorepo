#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

[[ "$1" == "smoke" ]] || private_die "private smoke stage mismatch"
private_require_command jq
private_require_command python3
private_require_target

agent_name="$(private_required_env_value HOSTED_AGENT_NAME)"
raw="$(cd "$PRIVATE_AZD_DIR" && private_azd ai agent invoke "$agent_name" "Resolve delayed order ORD-1001" --protocol responses --new-conversation --new-session --no-prompt)"
response="$(
  printf '%s\n' "$raw" |
    python3 "$SCRIPT_DIR/extract_azd_agent_json.py"
)" || private_die "private hosted smoke did not return JSON"
jq -e '.status == "completed"' <<<"$response" >/dev/null ||
  private_die "private hosted smoke did not complete"
conversation_id="$(
  jq -r '[.. | objects | (.thread_id? // .conversation_id? // empty)] | map(select(type == "string" and length > 0)) | .[0] // empty' \
    <<<"$response"
)"
[[ -n "$conversation_id" ]] || private_die "private hosted smoke did not return a conversation ID"

jq -n --arg conversation_id "$conversation_id" \
  '{conversation_id:$conversation_id,terminal_status:"completed",private_runner:true}'
