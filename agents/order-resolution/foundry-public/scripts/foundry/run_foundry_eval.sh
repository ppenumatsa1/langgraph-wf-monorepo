#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_AZD_DIR="${FOUNDRY_AZD_DIR:-$ROOT_DIR/infra/foundry-hosted}"
FOUNDRY_AZD_ENV_NAME="${FOUNDRY_AZD_ENV_NAME:-}"

usage() {
  echo "Usage: $0 [--check]" >&2
}

if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--check" ) ]]; then
  usage
  exit 2
fi

command -v azd >/dev/null 2>&1 || {
  echo "Missing required binary: azd" >&2
  exit 1
}

if [[ ! -f "$FOUNDRY_AZD_DIR/azure.yaml" ]]; then
  echo "Unable to locate Foundry AZD project at $FOUNDRY_AZD_DIR" >&2
  exit 1
fi

azd_args=(env get-value --cwd "$FOUNDRY_AZD_DIR" --no-prompt)
if [[ -n "$FOUNDRY_AZD_ENV_NAME" ]]; then
  azd_args+=(--environment "$FOUNDRY_AZD_ENV_NAME")
fi

read_azd_value() {
  local key="$1"
  local value
  if ! value="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd "${azd_args[@]}" "$key" 2>/dev/null)"; then
    echo "Unable to read $key from the selected Foundry AZD environment." >&2
    exit 1
  fi
  printf '%s' "$value"
}

export_required_azd_value() {
  local key="$1"
  local value
  value="$(read_azd_value "$key")"
  if [[ -z "$value" ]]; then
    echo "Missing required Foundry AZD environment value: $key" >&2
    exit 1
  fi
  export "$key=$value"
}

# Read only the evaluator's non-secret configuration. Do not source azd .env files
# or print values, since those files can contain unrelated credentials.
export_required_azd_value FOUNDRY_PROJECTS_ENDPOINT
export_required_azd_value FOUNDRY_MODEL_DEPLOYMENT_NAME

judge_model="$(AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd "${azd_args[@]}" FOUNDRY_EVAL_MODEL 2>/dev/null || true)"
if [[ -n "$judge_model" ]]; then
  export FOUNDRY_EVAL_MODEL="$judge_model"
fi

if [[ "${1:-}" == "--check" ]]; then
  if [[ -n "$FOUNDRY_AZD_ENV_NAME" ]]; then
    echo "Foundry evaluation configuration loaded from AZD environment: $FOUNDRY_AZD_ENV_NAME"
  else
    echo "Foundry evaluation configuration loaded from the selected AZD environment."
  fi
  exit 0
fi

wait_for_fresh_e2e_evidence() {
  local not_before="${FOUNDRY_E2E_EVIDENCE_NOT_BEFORE:-}"
  local evidence_file="${HOSTED_E2E_EVIDENCE_FILE:-$ROOT_DIR/backend/.foundry/results/hosted-e2e-evidence.json}"
  local max_attempts="${FOUNDRY_EVAL_EVIDENCE_MAX_ATTEMPTS:-240}"
  local poll_seconds="${FOUNDRY_EVAL_EVIDENCE_POLL_SECONDS:-5}"
  local generated_at

  [[ -n "$not_before" ]] || return 0
  command -v jq >/dev/null 2>&1 || {
    echo "Missing required binary while awaiting hosted E2E evidence: jq" >&2
    exit 1
  }

  for attempt in $(seq 1 "$max_attempts"); do
    if [[ -f "$evidence_file" ]]; then
      generated_at="$(jq -r '.generated_at // empty' "$evidence_file" 2>/dev/null || true)"
      if [[ -n "$generated_at" ]] &&
        [[ "$generated_at" == "$not_before" || "$generated_at" > "$not_before" ]]; then
        return 0
      fi
    fi
    echo "Awaiting fresh hosted E2E evidence for trace evaluation (${attempt}/${max_attempts})."
    sleep "$poll_seconds"
  done

  echo "Timed out waiting for hosted E2E evidence generated after this release began." >&2
  exit 1
}

wait_for_fresh_e2e_evidence

cd "$ROOT_DIR/backend"
exec "$ROOT_DIR/backend/.venv/bin/python" -m evals.foundry_eval_runner
