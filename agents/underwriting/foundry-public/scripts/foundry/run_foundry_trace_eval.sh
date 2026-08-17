#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -n "${RELEASE_ID:-}" ]]; then
  . "$ROOT_DIR/scripts/foundry/release_paths.sh"
  release_paths_configure "$ROOT_DIR"
fi
FOUNDRY_AZD_DIR="${FOUNDRY_AZD_DIR:-$ROOT_DIR/infra/foundry-hosted}"
FOUNDRY_AZD_ENV_NAME="${FOUNDRY_AZD_ENV_NAME:-}"
PYTHON="$ROOT_DIR/.venv/bin/python"

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

[[ -x "$PYTHON" ]] || {
  echo "Project virtual environment is required; run make install." >&2
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
  if ! value="$(azd "${azd_args[@]}" "$key" 2>/dev/null)"; then
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

export_required_azd_value FOUNDRY_PROJECTS_ENDPOINT
export_required_azd_value FOUNDRY_MODEL_DEPLOYMENT_NAME

if [[ "${1:-}" == "--check" ]]; then
  if [[ -n "$FOUNDRY_AZD_ENV_NAME" ]]; then
    echo "Foundry trace-eval configuration loaded from AZD environment: $FOUNDRY_AZD_ENV_NAME"
  else
    echo "Foundry trace-eval configuration loaded from the selected AZD environment."
  fi
  exit 0
fi

cd "$ROOT_DIR"
PYTHONPATH="$ROOT_DIR/backend" exec "$PYTHON" -m evals.foundry_trace_eval
