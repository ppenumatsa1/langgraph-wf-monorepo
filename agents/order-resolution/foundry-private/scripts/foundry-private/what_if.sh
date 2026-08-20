#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

private_require_command azd
private_require_command python3
private_require_file "$SCRIPT_DIR/what_if_guard.py"
private_require_target

private_azd provision --cwd "$PRIVATE_AZD_DIR" --preview --no-prompt 2>&1 |
  python3 "$SCRIPT_DIR/what_if_guard.py"

echo "Private Bicep what-if contains no Delete or Replace changes."
