#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
AZD_ENV_NAME="${AZURE_ENV_NAME:-order-resolution-azure-hosted}"

read_value() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$ROOT_DIR" --environment "$AZD_ENV_NAME" --no-prompt
}

export FOUNDRY_PROJECTS_ENDPOINT="$(read_value FOUNDRY_PROJECTS_ENDPOINT)"
export FOUNDRY_MODEL_DEPLOYMENT_NAME="$(read_value FOUNDRY_MODEL_DEPLOYMENT_NAME)"
export FOUNDRY_EVAL_MODEL="$(read_value FOUNDRY_EVAL_MODEL)"
export DOMAIN_E2E_EVIDENCE_FILE="${DOMAIN_E2E_EVIDENCE_FILE:-$ROOT_DIR/.artifacts/releases/${AZURE_RELEASE_ID:?AZURE_RELEASE_ID is required}/evidence/domain-e2e.json}"
export FOUNDRY_EVAL_EVIDENCE_FILE="${FOUNDRY_EVAL_EVIDENCE_FILE:-$ROOT_DIR/.artifacts/releases/$AZURE_RELEASE_ID/evidence/evaluation.json}"
export FOUNDRY_EVAL_ENFORCE_PASS="${FOUNDRY_EVAL_ENFORCE_PASS:-false}"

cd "$ROOT_DIR/backend"
exec "$ROOT_DIR/backend/.venv/bin/python" -m evals.foundry_eval_runner
