#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

release_id="$(private_release_id)"
"$SCRIPT_DIR/runner_exec.sh" smoke evidence/private-smoke-runner.json
details="$(jq -c '.details' "$(private_release_dir)/evidence/private-smoke-runner.json")"

jq -n \
  --arg release_id "$release_id" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --argjson details "$details" \
  '{schema_version:1,evidence_type:"hosted_smoke",status:"passed",release_id:$release_id,generated_at:$generated_at,conversation_id:$details.conversation_id,response_status:$details.terminal_status,private_runner:true}' |
  python3 "$SCRIPT_DIR/write_artifact.py" --release-id "$release_id" --relative-path evidence/hosted-smoke.json
