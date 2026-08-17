#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

evidence_dir="$(release_evidence_dir)"
frontend_url="$(jq -er '.frontend_url' "$evidence_dir/verification.json")"
PLAYWRIGHT_BASE_URL="$frontend_url" make -C "$ROOT_DIR" test-e2e
jq -n --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{status:"passed",generated_at:$generated_at}' >"$evidence_dir/browser-e2e.json"
