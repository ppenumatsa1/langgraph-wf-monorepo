#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

[[ "$1" == "runner_preflight" ]] || private_die "runner preflight stage mismatch"
for command in az azd curl docker git jq node npm psql python3; do
  private_require_command "$command"
done
private_require_target
private_assert_clean_source

subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
expected_commit="${FOUNDRY_PRIVATE_EXPECTED_COMMIT:-}"
[[ "$expected_commit" =~ ^[0-9a-f]{40}$ ]] ||
  private_die "runner requires a full immutable expected source commit"
runner_commit="$(git -C "$PRIVATE_ROOT_DIR" rev-parse HEAD)"
[[ "$runner_commit" == "$expected_commit" ]] ||
  private_die "runner source does not match the expected immutable commit"
[[ -x "$PRIVATE_ROOT_DIR/backend/.venv/bin/python" ]] ||
  private_die "runner checkout is missing backend/.venv"
[[ -d "$PRIVATE_ROOT_DIR/frontend/node_modules" ]] ||
  private_die "runner checkout is missing frontend/node_modules"
[[ -d "$PRIVATE_ROOT_DIR/scripts/playwright/node_modules" ]] ||
  private_die "runner checkout is missing scripts/playwright/node_modules"
private_require_file "$PRIVATE_ROOT_DIR/scripts/foundry-private/runner_stage.sh"
private_require_file "$PRIVATE_ROOT_DIR/scripts/foundry-private/runner_hosted_e2e.sh"
private_require_file "$PRIVATE_ROOT_DIR/scripts/foundry-private/runner_evaluation.sh"
private_require_file "$PRIVATE_ROOT_DIR/scripts/foundry-private/runner_telemetry.sh"
docker info >/dev/null ||
  private_die "runner Docker daemon is unavailable"

az login --identity --allow-no-subscriptions --output none ||
  private_die "runner managed identity authentication failed"
az account show --subscription "$subscription_id" --query id --output tsv |
  grep -Fxq "$subscription_id" ||
  private_die "runner Azure CLI is not authenticated to the private subscription"
private_azd auth login --check-status >/dev/null

jq -n \
  --arg commit "$runner_commit" \
  --arg subscription_id "$subscription_id" \
  '{runner_commit:$commit,subscription_id:$subscription_id,private_dns_execution:true}'
