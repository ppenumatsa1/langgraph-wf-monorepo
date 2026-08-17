#!/usr/bin/env bash
set -euo pipefail

API_BASE="${1:-http://localhost:8000}"
shift || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/run_manual_matrix.py" "$API_BASE" "$@"
