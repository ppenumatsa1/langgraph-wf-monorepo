#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/backend/.env.example}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Environment file not found: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

cd "$ROOT_DIR/backend"
if [[ ! -f ".venv/bin/activate" ]]; then
  echo "backend/.venv is missing. Run: make bootstrap" >&2
  exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate
exec python "$ROOT_DIR/infra/foundry-hosted/runtime/launch_backend.py"
