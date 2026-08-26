#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

private_require_command azd
private_require_command python3
private_require_file "$SCRIPT_DIR/what_if_guard.py"
private_require_target

expected_mode="${FOUNDRY_PRIVATE_INFRASTRUCTURE_MODE:-}"
[[ "$expected_mode" == "bootstrap" || "$expected_mode" == "reuse" ]] ||
  private_die "FOUNDRY_PRIVATE_INFRASTRUCTURE_MODE must explicitly select bootstrap or reuse"
actual_mode="$(private_azd_value INFRASTRUCTURE_MODE)"
[[ "$actual_mode" == "$expected_mode" ]] ||
  private_die "refusing ${actual_mode} preview when ${expected_mode} was explicitly requested"

private_azd provision --cwd "$PRIVATE_AZD_DIR" --preview --no-prompt 2>&1 |
  python3 "$SCRIPT_DIR/what_if_guard.py"

echo "Private Bicep ${actual_mode} what-if contains no Delete or Replace changes."
