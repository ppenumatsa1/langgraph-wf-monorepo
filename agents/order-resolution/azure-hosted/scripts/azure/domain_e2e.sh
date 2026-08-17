#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

evidence_dir="$(release_evidence_dir)"
frontend_url="$(jq -er '.frontend_url' "$evidence_dir/verification.json")"
output_file="$evidence_dir/domain-e2e.json"

python3 "$ROOT_DIR/scripts/manual/run_manual_matrix.py" "$frontend_url" \
  --case ORD-1001 --case ORD-1004 --case ORD-1009 \
  --request-timeout 90 --timeout 120 --poll 2 --json-output "$output_file"
