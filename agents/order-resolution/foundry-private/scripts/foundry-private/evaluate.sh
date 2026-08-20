#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

release_id="$(private_release_id)"
"$SCRIPT_DIR/runner_exec.sh" evaluation evidence/private-evaluation-runner.json
details="$(jq -c '.details' "$(private_release_dir)/evidence/private-evaluation-runner.json")"

jq -n \
  --arg release_id "$release_id" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --argjson details "$details" \
  '{schema_version:1,evidence_type:"evaluation",status:"completed",release_id:$release_id,generated_at:$generated_at,evaluation_name:$details.evaluation_name,run_name:$details.run_name,result_counts:$details.result_counts,trace_evaluation:$details.trace_evaluation,report_only:true,fresh_workflow_snapshots:true}' |
  python3 "$SCRIPT_DIR/write_artifact.py" --release-id "$release_id" --relative-path evidence/evaluation.json
