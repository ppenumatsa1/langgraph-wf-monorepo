#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

private_require_command azd
profile_path="${FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE:-}"
[[ -n "$profile_path" ]] ||
  private_die "FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE is required for private provisioning"

"$SCRIPT_DIR/apply_profile.sh"
private_require_target
"$SCRIPT_DIR/bootstrap_env.sh"
"$SCRIPT_DIR/iac_contract.sh"
private_azd_set INFRASTRUCTURE_MODE bootstrap
private_azd_set DEPLOY_FOUNDRY_READY_RESOURCES false
FOUNDRY_PRIVATE_INFRASTRUCTURE_MODE=bootstrap "$SCRIPT_DIR/what_if.sh"
private_azd provision --cwd "$PRIVATE_AZD_DIR" --no-prompt
"$SCRIPT_DIR/wait_foundry_ready.sh"
private_azd_set DEPLOY_FOUNDRY_READY_RESOURCES true
FOUNDRY_PRIVATE_INFRASTRUCTURE_MODE=bootstrap "$SCRIPT_DIR/what_if.sh"
private_azd provision --cwd "$PRIVATE_AZD_DIR" --no-prompt
"$SCRIPT_DIR/reconcile.sh"
private_azd_set INFRASTRUCTURE_MODE reuse
"$SCRIPT_DIR/runner_bootstrap.sh"
"$SCRIPT_DIR/postgres.sh" schema
"$SCRIPT_DIR/postgres.sh" credentials
"$SCRIPT_DIR/postgres.sh" readiness

echo "One-time foundry-private provisioning, reconciliation, and PostgreSQL bootstrap completed."
