#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

private_require_command jq
private_require_command make
private_require_command python3
profile_path="${FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE:-}"
[[ -n "$profile_path" ]] ||
  private_die "FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE is required"

export FOUNDRY_PRIVATE_RELEASE_ID="${FOUNDRY_PRIVATE_RELEASE_ID:-langgraph-order-resolution-private-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
export FOUNDRY_PRIVATE_RELEASE_STARTED_AT="${FOUNDRY_PRIVATE_RELEASE_STARTED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
release_id="$(private_release_id)"
release_script="$PRIVATE_ROOT_DIR/scripts/foundry/release_evidence.py"

python3 "$release_script" init \
  --release-id "$release_id" \
  --started-at "$FOUNDRY_PRIVATE_RELEASE_STARTED_AT" \
  --profile "$profile_path" \
  --executor private-runner

release_initialized=1
release_finalized=0
current_stage=initialization
finalize_failure() {
  local exit_code=$?
  if [[ "$exit_code" -ne 0 && "$release_initialized" -eq 1 && "$release_finalized" -eq 0 ]]; then
    if ! python3 "$release_script" finalize \
      --release-id "$release_id" \
      --status failed \
      --failed-stage "$current_stage" \
      --error "Private release stage failed; inspect the bounded runner operation result."; then
      printf 'foundry-private: unable to record failed release evidence\n' >&2
    fi
  fi
  return "$exit_code"
}
trap finalize_failure EXIT

timing() {
  local stage="$1"
  local action="$2"
  local status="${3:-}"
  local timestamp="${4:-}"
  local args=(timing --release-id "$release_id" --stage "$stage" --action "$action")
  [[ -n "$status" ]] && args+=(--status "$status")
  [[ -n "$timestamp" ]] && args+=(--timestamp "$timestamp")
  python3 "$release_script" "${args[@]}" >/dev/null
}

run_stage() {
  local stage="$1"
  shift
  current_stage="$stage"
  timing "$stage" start
  if "$@"; then
    timing "$stage" end succeeded
  else
    local status=$?
    timing "$stage" end failed
    return "$status"
  fi
}

current_stage=profile_apply
"$SCRIPT_DIR/apply_profile.sh"
private_require_target

timing app_only start
FOUNDRY_PRIVATE_RUN_FULL_LOCAL_GATES=1 \
  run_stage local_gates "$SCRIPT_DIR/local_gates.sh"
run_stage runner_bootstrap "$SCRIPT_DIR/runner_bootstrap.sh"
run_stage runner_preflight "$SCRIPT_DIR/runner_exec.sh" runner_preflight evidence/private-runner-preflight.json
run_stage private_readiness bash -c "
  '$SCRIPT_DIR/model_preflight.sh' &&
  '$SCRIPT_DIR/postgres.sh' readiness
"
run_stage package_build "$SCRIPT_DIR/package.sh"
run_stage backend_deployment "$SCRIPT_DIR/deploy.sh" backend
run_stage frontend_deployment "$SCRIPT_DIR/deploy.sh" frontend
run_stage hosted_deployment_activation "$SCRIPT_DIR/deploy.sh" hosted
run_stage verification "$SCRIPT_DIR/verify.sh"
run_stage smoke "$SCRIPT_DIR/smoke.sh"
run_stage hosted_e2e "$SCRIPT_DIR/hosted_e2e.sh"
run_stage browser_e2e "$SCRIPT_DIR/browser_e2e.sh"
run_stage evaluation "$SCRIPT_DIR/evaluate.sh"
run_stage telemetry "$SCRIPT_DIR/telemetry.sh"

telemetry_ended_at="$(
  jq -er '.extensions.release_timing.stages.telemetry.ended_at' \
    "$(private_release_dir)/release.json"
)"
timing app_only end succeeded "$telemetry_ended_at"
current_stage=final_evidence
timing final_evidence start
python3 "$release_script" aggregate --release-id "$release_id" >/dev/null
timing final_evidence end succeeded
python3 "$release_script" finalize --release-id "$release_id" --status succeeded >/dev/null
release_finalized=1

printf 'Foundry-private app-only release completed: %s\n' "$release_id"
