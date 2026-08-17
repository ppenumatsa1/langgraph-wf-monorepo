#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

require_bin az
require_bin azd
require_bin make

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

FOUNDRY_RELEASE_BASE_REF="${FOUNDRY_RELEASE_BASE_REF:-HEAD}"
FOUNDRY_VALIDATION_MODE="${FOUNDRY_VALIDATION_MODE:-}"
FOUNDRY_SMOKE_MODE="${FOUNDRY_SMOKE_MODE:-happy}"
FOUNDRY_DEPLOYMENT_PROFILE="${FOUNDRY_DEPLOYMENT_PROFILE:-$ROOT_DIR/deployment/profiles/foundry-public.env}"

if [[ -n "${FOUNDRY_DEPLOY_MODE:-}" ]]; then
  echo "FOUNDRY_DEPLOY_MODE overrides are forbidden; routine releases are always app_only." >&2
  exit 2
fi

if [[ -n "$(git status --porcelain --untracked-files=normal -- .)" ]]; then
  echo "Release requires a clean lane worktree committed at HEAD." >&2
  exit 2
fi

. "$ROOT_DIR/scripts/foundry/release_paths.sh"
release_paths_configure "$ROOT_DIR"

if ! git rev-parse --verify --quiet HEAD^{commit} >/dev/null; then
  if [[ "$FOUNDRY_RELEASE_BASE_REF" == "HEAD" ]]; then
    FOUNDRY_RELEASE_BASE_REF="$(git hash-object -t tree /dev/null)"
  fi
fi

bash "$ROOT_DIR/deployment/apply-azd-profile.sh" "$FOUNDRY_DEPLOYMENT_PROFILE"

profile_value() {
  sed -n "s/^$1=//p" "$FOUNDRY_DEPLOYMENT_PROFILE" | tail -n 1
}

repository="$(git config --get remote.origin.url || printf 'local-worktree')"
commit="$(git rev-parse HEAD 2>/dev/null || git hash-object -t tree /dev/null)"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/foundry/release_record.py" init \
  --release-id "$RELEASE_ID" \
  --repository "$repository" \
  --commit "$commit" \
  --profile "$FOUNDRY_DEPLOYMENT_PROFILE" \
  --environment "$(profile_value AZURE_ENV_NAME)" \
  --subscription-id "$(profile_value AZURE_SUBSCRIPTION_ID)" \
  --resource-group "$(profile_value AZURE_RESOURCE_GROUP)" \
  --location "$(profile_value AZURE_LOCATION)" \
  --executor "${GITHUB_ACTOR:-local-operator}" \
  --required-gate verification \
  --required-gate postgres_readiness \
  --required-gate model_preflight \
  --required-gate hosted_e2e \
  --required-gate hosted_smoke \
  --required-gate trace_evaluation \
  --required-gate application_insights >/dev/null

release_finalized=false
release_stage=bootstrap
active_timing_stage=
timing() {
  "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/foundry/release_record.py" timing \
    --release-id "$RELEASE_ID" "$@"
}

run_timed_stage() {
  local stage=$1
  shift
  active_timing_stage="$stage"
  timing --stage "$stage" --action start
  if "$@"; then
    timing --stage "$stage" --action succeed
    active_timing_stage=
  else
    local status=$?
    timing --stage "$stage" --action fail || true
    active_timing_stage=
    return "$status"
  fi
}

finalize_failed_release() {
  local exit_code=$?
  if [[ "$release_finalized" != true ]]; then
    if [[ -n "$active_timing_stage" ]]; then
      timing --stage "$active_timing_stage" --action fail >/dev/null 2>&1 || true
    fi
    "$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/foundry/release_record.py" finalize \
      --release-id "$RELEASE_ID" \
      --status failed \
      --failed-stage "$release_stage" \
      --error "Release stage failed; inspect lane-local logs." >/dev/null || true
  fi
  exit "$exit_code"
}
trap finalize_failed_release EXIT
exec > >(tee -a "$FOUNDRY_RELEASE_LOG_DIR/release.log") 2>&1

./scripts/foundry/ensure_foundry_azd_defaults.sh

wait_for_parallel_jobs() {
  local status=0
  local pid
  for pid in "$@"; do
    if ! wait "$pid"; then
      status=1
    fi
  done
  return "$status"
}

router_output="$(./scripts/skills/deployment-mode-router.sh "$FOUNDRY_RELEASE_BASE_REF")"
printf '%s\n' "$router_output"

deploy_mode="$(printf '%s\n' "$router_output" | sed -n 's/^deploy_mode=//p' | tail -n 1)"
validation_mode="$(printf '%s\n' "$router_output" | sed -n 's/^validation_mode=//p' | tail -n 1)"
reason="$(printf '%s\n' "$router_output" | sed -n 's/^reason=//p' | tail -n 1)"

if [[ -n "$FOUNDRY_VALIDATION_MODE" ]]; then
  validation_mode="$FOUNDRY_VALIDATION_MODE"
fi

echo "Release router selected deploy_mode=${deploy_mode} validation_mode=${validation_mode} reason=${reason} base_ref=${FOUNDRY_RELEASE_BASE_REF}"

case "$validation_mode" in
  quick)
    validation_target=validate-quick
    ;;
  full)
    validation_target=validate-full
    ;;
  *)
    echo "Unsupported validation mode: $validation_mode" >&2
    exit 1
    ;;
esac

make "$validation_target" &
release_stage=local_validation
validation_pid=$!
make foundry-iac-build &
iac_pid=$!
wait_for_parallel_jobs "$validation_pid" "$iac_pid"

case "$deploy_mode" in
  app_only)
    make foundry-release-readiness
    release_stage=package_build
    active_timing_stage=package_build
    timing --stage package_build --action start --start-app-only
    if make foundry-release-package; then
      timing --stage package_build --action succeed
      active_timing_stage=
    else
      status=$?
      timing --stage package_build --action fail || true
      active_timing_stage=
      exit "$status"
    fi
    release_stage=image_build
    run_timed_stage image_build make foundry-release-build
    release_stage=hosted_activation
    run_timed_stage hosted_activation make foundry-release-hosted-activate
    release_stage=aca_deployment
    run_timed_stage aca_deployment make foundry-release-app-deploy
    ;;
  *)
    echo "Release router contract violation: deploy_mode must be app_only, got: $deploy_mode" >&2
    exit 1
    ;;
esac

release_stage=smoke
run_timed_stage smoke env SMOKE_MODE="$FOUNDRY_SMOKE_MODE" make foundry-smoke
release_stage=evaluation
(run_timed_stage evaluation make foundry-eval) &
evaluation_pid=$!
release_stage=deployed_e2e
if ! run_timed_stage deployed_e2e make foundry-hosted-e2e; then
  wait "$evaluation_pid" || true
  exit 1
fi
release_stage=telemetry
run_timed_stage telemetry make foundry-telemetry
if ! wait "$evaluation_pid"; then
  release_stage=evaluation
  exit 1
fi
release_stage=deployment_verification
run_timed_stage deployment_verification make foundry-verify
release_stage=final_evidence
active_timing_stage=final_evidence
timing --stage final_evidence --action start
make foundry-evidence
active_timing_stage=
release_finalized=true
trap - EXIT

echo "Underwriting Foundry public release completed."
