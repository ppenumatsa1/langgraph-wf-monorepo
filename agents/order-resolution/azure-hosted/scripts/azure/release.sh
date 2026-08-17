#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
cd "$ROOT_DIR"

export AZURE_RELEASE_ID="${AZURE_RELEASE_ID:-order-resolution-azure-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
profile="${AZURE_DEPLOYMENT_PROFILE:-deployment/profiles/azure-hosted.env}"
python3 scripts/azure/release_evidence.py init --release-id "$AZURE_RELEASE_ID" --profile "$profile"
current_stage=initialization
completed=0
on_exit() {
  local status=$?
  if [[ "$status" -ne 0 && "$completed" -eq 0 ]]; then
    python3 scripts/azure/release_evidence.py finalize-failed \
      --release-id "$AZURE_RELEASE_ID" --failed-stage "$current_stage" || true
  fi
  return "$status"
}
trap on_exit EXIT

timed() {
  local stage="$1"
  shift
  current_stage="$stage"
  python3 scripts/azure/release_evidence.py timing --release-id "$AZURE_RELEASE_ID" --stage "$stage" --action start
  if "$@"; then
    python3 scripts/azure/release_evidence.py timing --release-id "$AZURE_RELEASE_ID" --stage "$stage" --action end --status succeeded
  else
    python3 scripts/azure/release_evidence.py timing --release-id "$AZURE_RELEASE_ID" --stage "$stage" --action end --status failed || true
    return 1
  fi
}

timed preflight scripts/azure/preflight.sh
make validate-full &
validation_pid=$!
make azure-iac-build &
iac_pid=$!
wait "$validation_pid"
wait "$iac_pid"
timed model_preflight scripts/azure/preflight_models.sh
timed images scripts/azure/build_images.sh
timed deployment scripts/azure/deploy_apps.sh
timed verification scripts/azure/verify_deployment.sh
timed smoke scripts/azure/smoke.sh
timed domain_e2e scripts/azure/domain_e2e.sh
timed browser_e2e scripts/azure/browser_e2e.sh
timed evaluation make azure-eval &
evaluation_pid=$!
timed telemetry make azure-telemetry &
telemetry_pid=$!
wait "$evaluation_pid"
wait "$telemetry_pid"
python3 scripts/azure/release_evidence.py aggregate --release-id "$AZURE_RELEASE_ID"
completed=1
echo "Azure-hosted app-only release completed: $AZURE_RELEASE_ID"
