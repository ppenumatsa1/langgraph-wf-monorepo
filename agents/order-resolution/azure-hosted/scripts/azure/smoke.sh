#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

evidence_dir="$(release_evidence_dir)"
frontend_url="$(jq -er '.frontend_url' "$evidence_dir/verification.json")"
curl -fsS --max-time 60 "$frontend_url/health" | grep -Fxq ok
curl -fsS --max-time 60 "$frontend_url/api/health" | jq -e '.status == "ok"' >/dev/null
jq -n --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '{status:"passed",generated_at:$generated_at,frontend_health:true,proxy_health:true}' \
  >"$evidence_dir/smoke.json"
