#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

evidence_dir="$(release_evidence_dir)"
frontend_url="$(jq -er '.frontend_url' "$evidence_dir/verification.json")"
output_file="$evidence_dir/domain-e2e.json"
release_id="${AZURE_RELEASE_ID:?AZURE_RELEASE_ID is required}"
stamped_output="$(mktemp "$evidence_dir/.domain-e2e.XXXXXX")"
trap 'rm -f "$stamped_output"' EXIT

python3 "$ROOT_DIR/scripts/manual/run_manual_matrix.py" "$frontend_url" \
  --case ORD-1001 --case ORD-1004 --case ORD-1009 \
  --request-timeout 90 --timeout 120 --poll 2 --json-output "$output_file"

jq --arg release_id "$release_id" '. + {release_id: $release_id}' \
  "$output_file" >"$stamped_output"
mv "$stamped_output" "$output_file"
