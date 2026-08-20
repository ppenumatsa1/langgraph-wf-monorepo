#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

release_id="$(private_release_id)"
"$SCRIPT_DIR/runner_exec.sh" hosted_e2e evidence/private-hosted-e2e-runner.json
details="$(jq -c '.details' "$(private_release_dir)/evidence/private-hosted-e2e-runner.json")"

jq -e '(.conversation_ids | type == "array" and length == 3 and unique | length == 3)' <<<"$details" >/dev/null ||
  private_die "private hosted E2E evidence must contain three unique conversations"
jq -n \
  --arg release_id "$release_id" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --argjson details "$details" \
  '{schema_version:1,evidence_type:"hosted_e2e",status:"passed",release_id:$release_id,generated_at:$generated_at,started_at:$details.started_at,conversation_ids:$details.conversation_ids,scenarios:$details.scenarios,low_risk_thread_id:$details.low_risk_thread_id,approved_thread_id:$details.approved_thread_id,damaged_item_thread_id:$details.damaged_item_thread_id,private_runner:true}' |
  python3 "$SCRIPT_DIR/write_artifact.py" --release-id "$release_id" --relative-path evidence/hosted-e2e.json
