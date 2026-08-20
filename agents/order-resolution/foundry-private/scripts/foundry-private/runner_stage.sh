#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

[[ "${FOUNDRY_PRIVATE_RUNNER_EXECUTION:-}" == "1" ]] ||
  private_die "runner stages may only execute through Azure Run Command"
[[ $# -eq 1 ]] || private_die "runner stage is required"
stage="$1"
release_id="$(private_release_id)"
environment="${FOUNDRY_PRIVATE_AZD_ENV_NAME:-}"
[[ "$environment" == "$PRIVATE_EXPECTED_ENVIRONMENT" ]] ||
  private_die "runner requires the private AZD environment"

private_require_command azd
private_require_command git
private_require_command jq
private_require_command python3
expected_commit="${FOUNDRY_PRIVATE_EXPECTED_COMMIT:-}"
[[ "$expected_commit" =~ ^[0-9a-f]{40}$ ]] ||
  private_die "runner requires a full immutable expected source commit"
[[ "$(git -C "$PRIVATE_ROOT_DIR" rev-parse HEAD)" == "$expected_commit" ]] ||
  private_die "runner source does not match the release source commit"
private_azd env select "$environment" --cwd "$PRIVATE_AZD_DIR" --no-prompt

case "$stage" in
  runner_preflight)
    stage_script="$SCRIPT_DIR/runner_preflight.sh"
    ;;
  postgres_schema|postgres_credentials|postgres_readiness)
    stage_script="$SCRIPT_DIR/runner_postgres.sh"
    ;;
  acr_package)
    stage_script="$SCRIPT_DIR/runner_acr_package.sh"
    ;;
  deploy_backend|deploy_frontend|deploy_hosted)
    stage_script="$SCRIPT_DIR/runner_deploy_runtime.sh"
    ;;
  verify_runtime)
    stage_script="$SCRIPT_DIR/runner_verify_runtime.sh"
    ;;
  smoke)
    stage_script="$SCRIPT_DIR/runner_smoke.sh"
    ;;
  hosted_e2e)
    stage_script="$SCRIPT_DIR/runner_hosted_e2e.sh"
    ;;
  browser_e2e)
    stage_script="$SCRIPT_DIR/runner_browser_e2e.sh"
    ;;
  evaluation)
    stage_script="$SCRIPT_DIR/runner_evaluation.sh"
    ;;
  telemetry)
    stage_script="$SCRIPT_DIR/runner_telemetry.sh"
    ;;
  *)
    private_die "unsupported private runner stage: $stage"
    ;;
esac

private_require_file "$stage_script"
error_dir="$PRIVATE_ROOT_DIR/.artifacts/private-runner-logs/$release_id"
error_log="$error_dir/${stage}.stderr.log"
mkdir -p "$error_dir"
chmod 700 "$error_dir"
if ! details="$("$stage_script" "$stage" 2>"$error_log")"; then
  printf 'Private runner stage failed: %s\n' "$stage" >&2
  tail -c 1500 "$error_log" |
    sed -E \
      -e 's#postgresql(\+psycopg)?://[^[:space:]]+#postgresql://[REDACTED]#g' \
      -e 's#([Pp]assword|[Tt]oken|[Ss]ecret)[=:][^[:space:]]+#\1=[REDACTED]#g' >&2
  exit 1
fi
details="$(jq -c . <<<"$details")"
jq -e 'type == "object"' <<<"$details" >/dev/null ||
  private_die "runner stage returned invalid structured evidence"
(( ${#details} <= 2200 )) ||
  private_die "runner stage evidence exceeds the bounded Run Command transport"

RUNNER_STAGE="$stage" \
RUNNER_RELEASE_ID="$release_id" \
RUNNER_DETAILS="$details" \
python3 - <<'PY' | base64 -w0 | sed 's/^/FOUNDRY_PRIVATE_RUNNER_EVIDENCE_B64=/'
import json
import os
from datetime import datetime, timezone

details = json.loads(os.environ["RUNNER_DETAILS"])
payload = {
    "schema_version": 1,
    "evidence_type": "private_runner_stage",
    "status": "passed",
    "release_id": os.environ["RUNNER_RELEASE_ID"],
    "stage": os.environ["RUNNER_STAGE"],
    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "details": details,
}
print(json.dumps(payload, separators=(",", ":")))
PY
