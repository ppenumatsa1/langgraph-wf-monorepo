#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

release_id="$(private_release_id)"
"$SCRIPT_DIR/runner_exec.sh" telemetry evidence/private-telemetry-runner.json
details="$(jq -c '.details' "$(private_release_dir)/evidence/private-telemetry-runner.json")"

jq -n \
  --arg release_id "$release_id" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --argjson details "$details" \
  '{
    schema_version: 1,
    evidence_type: "telemetry",
    status: "passed",
    release_id: $release_id,
    generated_at: $generated_at,
    started_at: $details.started_at,
    conversation_ids: $details.conversation_ids,
    matched_count: $details.matched_count,
    telemetry_rows: $details.telemetry_rows,
    exception_rows: $details.exception_rows,
    correlation: "Application Insights conversation correlation",
    private_runner: true
  }' |
  python3 "$SCRIPT_DIR/write_artifact.py" --release-id "$release_id" --relative-path evidence/telemetry.json
