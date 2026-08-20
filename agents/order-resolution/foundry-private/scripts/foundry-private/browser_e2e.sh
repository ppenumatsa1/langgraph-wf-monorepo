#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

release_id="$(private_release_id)"
"$SCRIPT_DIR/runner_exec.sh" browser_e2e evidence/private-browser-e2e-runner.json
details="$(jq -c '.details' "$(private_release_dir)/evidence/private-browser-e2e-runner.json")"

jq -n \
  --arg release_id "$release_id" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --argjson details "$details" \
  '{schema_version:1,evidence_type:"browser_e2e",status:"passed",release_id:$release_id,generated_at:$generated_at,private_runner:true,details:$details}' |
  python3 "$SCRIPT_DIR/write_artifact.py" --release-id "$release_id" --relative-path evidence/browser-e2e.json
