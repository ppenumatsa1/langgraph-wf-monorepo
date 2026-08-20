#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
"$SCRIPT_DIR/runner_exec.sh" acr_package evidence/private-acr-packaging.json
