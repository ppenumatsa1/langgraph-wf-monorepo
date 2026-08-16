#!/usr/bin/env bash
set -euo pipefail

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1"
    exit 1
  }
}

require_bin az
require_bin azd
require_bin make
require_bin jq
require_bin python3

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

shared_profile="$ROOT_DIR/../deployment/profiles/foundry-public.env"
legacy_profile="$ROOT_DIR/deployment/profiles/foundry-public.env"
if [[ -n "${FOUNDRY_DEPLOYMENT_PROFILE:-}" ]]; then
  deployment_profile="$FOUNDRY_DEPLOYMENT_PROFILE"
elif [[ -f "$shared_profile" ]]; then
  deployment_profile="$shared_profile"
else
  deployment_profile="$legacy_profile"
  echo "WARN: Using legacy lane-local deployment profile; migrate to $shared_profile." >&2
fi
if [[ "$deployment_profile" == "$legacy_profile" ]]; then
  echo "WARN: $legacy_profile is legacy_pending_cutover; prefer $shared_profile." >&2
fi
[[ -f "$deployment_profile" && ! -L "$deployment_profile" ]] || {
  echo "Deployment profile must be a regular non-symlink file: $deployment_profile" >&2
  exit 1
}

FOUNDRY_AZD_ENV_NAME="${FOUNDRY_AZD_ENV_NAME:-${AZD_ENV_NAME:-}}"
FOUNDRY_RELEASE_BASE_REF="${FOUNDRY_RELEASE_BASE_REF:-HEAD}"
FOUNDRY_VALIDATION_MODE="${FOUNDRY_VALIDATION_MODE:-}"

if [[ -n "${FOUNDRY_DEPLOY_MODE:-}" ]]; then
  echo "FOUNDRY_DEPLOY_MODE is no longer supported; automatic releases are app_only." >&2
  exit 1
fi

export FOUNDRY_RELEASE_STARTED_AT="${FOUNDRY_RELEASE_STARTED_AT:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
export FOUNDRY_RELEASE_ID="${FOUNDRY_RELEASE_ID:-langgraph-order-resolution-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
release_dir="$ROOT_DIR/.artifacts/releases/$FOUNDRY_RELEASE_ID"
export FOUNDRY_RELEASE_LOG_DIR="$release_dir/logs"
export FOUNDRY_RELEASE_CONTEXT_FILE="$release_dir/release.json"
export FOUNDRY_MODEL_PREFLIGHT_EVIDENCE_FILE="$release_dir/evidence/model-preflight.json"
export FOUNDRY_DEPLOYMENT_VERIFICATION_FILE="$release_dir/evidence/deployment-verification.json"
export HOSTED_SMOKE_EVIDENCE_FILE="$release_dir/evidence/hosted-smoke.json"
export FOUNDRY_E2E_EVIDENCE_FILE="$release_dir/evidence/hosted-e2e.json"
export HOSTED_E2E_EVIDENCE_FILE="$FOUNDRY_E2E_EVIDENCE_FILE"
export APPINSIGHTS_CONNECTION_EVIDENCE_FILE="$release_dir/evidence/appinsights-connection.json"
export APPINSIGHTS_EVIDENCE_FILE="$release_dir/evidence/telemetry.json"
export FOUNDRY_EVAL_EVIDENCE_FILE="$release_dir/evidence/evaluation.json"
export PUBLIC_BACKEND_DEPLOYMENT_METADATA_FILE="$release_dir/evidence/backend-deployment.json"
export PUBLIC_FRONTEND_DEPLOYMENT_METADATA_FILE="$release_dir/evidence/frontend-deployment.json"
export HOSTED_AGENT_DEPLOYMENT_METADATA_FILE="$release_dir/evidence/hosted-agent-deployment.json"
export FOUNDRY_RUNTIME_CONNECTION_METADATA_FILE="$release_dir/evidence/runtime-connection-deployment.json"

release_initialized=0
release_finalized=0
release_stage=initialization
timing() {
  if [[ -n "${3:-}" ]]; then
    python3 scripts/foundry/release_evidence.py timing \
      --release-id "$FOUNDRY_RELEASE_ID" \
      --stage "$1" \
      --action "$2" \
      --status "$3" \
      >/dev/null
  else
    python3 scripts/foundry/release_evidence.py timing \
      --release-id "$FOUNDRY_RELEASE_ID" \
      --stage "$1" \
      --action "$2" \
      >/dev/null
  fi
}
run_timed_stage() {
  local stage="$1"
  shift
  timing "$stage" start
  if "$@"; then
    timing "$stage" end succeeded
  else
    local exit_code=$?
    timing "$stage" end failed || true
    return "$exit_code"
  fi
}
finalize_failed_release() {
  local exit_code=$?
  if [[ "$exit_code" -ne 0 && "$release_initialized" -eq 1 && "$release_finalized" -eq 0 ]]; then
    python3 scripts/foundry/release_evidence.py finalize \
      --release-id "$FOUNDRY_RELEASE_ID" \
      --status failed \
      --failed-stage "$release_stage" \
      --error "Release stage failed; inspect local logs outside the sanitized release record." \
      >/dev/null 2>&1 || true
  fi
  return "$exit_code"
}
trap finalize_failed_release EXIT

python3 scripts/foundry/release_evidence.py init \
  --release-id "$FOUNDRY_RELEASE_ID" \
  --started-at "$FOUNDRY_RELEASE_STARTED_AT" \
  --profile "$deployment_profile" \
  --executor local
release_initialized=1

release_stage=environment_selection
if [[ -n "$FOUNDRY_AZD_ENV_NAME" ]]; then
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env select "$FOUNDRY_AZD_ENV_NAME" --cwd infra/foundry-hosted --no-prompt
fi
./scripts/foundry/ensure_foundry_azd_defaults.sh

get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd infra/foundry-hosted --no-prompt 2>/dev/null || true
}

required_env() {
  local name="$1"
  local value
  value="$(get_env "$name")"
  if [[ -z "$value" ]]; then
    echo "Missing selected AZD environment value: $name" >&2
    exit 1
  fi
  printf '%s' "$value"
}

AZURE_SUBSCRIPTION_ID="$(required_env AZURE_SUBSCRIPTION_ID)"
AZURE_RESOURCE_GROUP="$(required_env AZURE_RESOURCE_GROUP)"
AZURE_LOCATION="$(required_env AZURE_LOCATION)"
POSTGRES_SERVER_NAME="$(required_env POSTGRES_SERVER_NAME)"
RUNTIME_DATABASE_URL="$(required_env RUNTIME_DATABASE_URL)"
if [[ -z "$RUNTIME_DATABASE_URL" ]]; then
  echo "RUNTIME_DATABASE_URL (or DATABASE_URL) is required."
  exit 1
fi
if [[ "$RUNTIME_DATABASE_URL" != *"sslmode=require"* ]]; then
  echo "RUNTIME_DATABASE_URL must include sslmode=require."
  exit 1
fi
if [[ "$RUNTIME_DATABASE_URL" != *"${POSTGRES_SERVER_NAME}.postgres.database.azure.com"* ]]; then
  echo "RUNTIME_DATABASE_URL must target ${POSTGRES_SERVER_NAME}.postgres.database.azure.com."
  exit 1
fi
if [[ ! -f backend/Dockerfile.hosted || ! -f infra/foundry-hosted/runtime/launch_hosted_agent.py ]]; then
  echo "Hosted source validation failed: backend/Dockerfile.hosted and the stable hosted launcher are required."
  exit 1
fi
if [[ ! -f backend/foundry/main.py && ! -f backend/app/langgraph/foundry_public.py && ! -f backend/app/langgraph/foundry.py && ! -f backend/app/langgraph/hosted.py ]]; then
  echo "Hosted source validation failed: no supported backend/app/langgraph or backend/foundry hosted entrypoint was found." >&2
  exit 1
fi

az account set --subscription "$AZURE_SUBSCRIPTION_ID"
az account show --query id -o tsv | grep -qx "$AZURE_SUBSCRIPTION_ID"
AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd auth login --check-status >/dev/null

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
infrastructure_reconciliation="$(printf '%s\n' "$router_output" | sed -n 's/^infrastructure_reconciliation=//p' | tail -n 1)"
reason="$(printf '%s\n' "$router_output" | sed -n 's/^reason=//p' | tail -n 1)"

if [[ -n "$FOUNDRY_VALIDATION_MODE" ]]; then
  validation_mode="$FOUNDRY_VALIDATION_MODE"
fi

if [[ "$deploy_mode" != "app_only" ]]; then
  echo "Automatic release routing must remain app_only; received: $deploy_mode" >&2
  exit 1
fi

echo "Release router selected deploy_mode=${deploy_mode} validation_mode=${validation_mode} infrastructure_reconciliation=${infrastructure_reconciliation} reason=${reason} base_ref=${FOUNDRY_RELEASE_BASE_REF}"

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

(
  unset RUNTIME_DATABASE_URL DATABASE_URL
  make "$validation_target"
) &
validation_pid=$!
release_stage=local_validation
make foundry-iac-build &
iac_pid=$!
wait_for_parallel_jobs "$validation_pid" "$iac_pid"

release_stage=deployment
timing app_only start
make foundry-release-deploy
release_stage=deployment_verification
run_timed_stage verification make foundry-verify

release_stage=hosted_smoke
run_timed_stage smoke make foundry-smoke
FOUNDRY_E2E_EVIDENCE_NOT_BEFORE="$FOUNDRY_RELEASE_STARTED_AT" \
  run_timed_stage evaluation make foundry-eval &
evaluation_pid=$!
release_stage=hosted_e2e
if ! run_timed_stage hosted_e2e make foundry-hosted-e2e; then
  echo "Hosted E2E failed; cancelling the pending trace evaluation." >&2
  kill "$evaluation_pid" 2>/dev/null || true
  wait "$evaluation_pid" || true
  exit 1
fi

release_stage=telemetry
run_timed_stage telemetry make foundry-telemetry &
telemetry_pid=$!
wait_for_parallel_jobs "$evaluation_pid" "$telemetry_pid"
telemetry_ended_at="$(jq -er '.extensions.release_timing.stages.telemetry.ended_at' "$FOUNDRY_RELEASE_CONTEXT_FILE")"
python3 scripts/foundry/release_evidence.py timing \
  --release-id "$FOUNDRY_RELEASE_ID" \
  --stage app_only \
  --action end \
  --status succeeded \
  --timestamp "$telemetry_ended_at" \
  >/dev/null
release_stage=release_evidence
make foundry-evidence
release_finalized=1

echo "Order Resolution LangGraph Foundry public app-only release completed for ${AZURE_SUBSCRIPTION_ID}/${AZURE_RESOURCE_GROUP}."
