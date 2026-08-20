#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

[[ $# -eq 1 ]] || {
  printf 'Usage: %s <runner-stage>\n' "$0" >&2
  exit 2
}
stage="$1"
case "$stage" in
  postgres_schema|postgres_credentials|postgres_readiness) ;;
  *) private_die "manual private runner stage is not permitted: $stage" ;;
esac

for command in az git python3; do
  private_require_command "$command"
done
private_require_target
private_assert_clean_source
subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
environment="$(private_azd_value AZURE_ENV_NAME)"
runner_group="$(private_runner_resource_group)"
runner_name="$(private_runner_name)"
runner_workdir="$(private_runner_workdir)"
release_id="manual-private-${stage}-$(date -u +%Y%m%dT%H%M%SZ)-$$"
expected_commit="$(git -C "$PRIVATE_ROOT_DIR" rev-parse HEAD)"
power_state="$(
  az vm get-instance-view --subscription "$subscription_id" --resource-group "$runner_group" \
    --name "$runner_name" \
    --query "instanceView.statuses[?code=='PowerState/running'] | length(@)" --output tsv
)"
[[ "$power_state" == "1" ]] || private_die "private runner VM must be running"

printf -v remote_command \
  'set -euo pipefail; cd %q; export AZURE_DEV_USER_AGENT=%q FOUNDRY_PRIVATE_RUNNER_EXECUTION=1 FOUNDRY_PRIVATE_RELEASE_ID=%q FOUNDRY_PRIVATE_AZD_ENV_NAME=%q FOUNDRY_PRIVATE_EXPECTED_COMMIT=%q; exec bash scripts/foundry-private/runner_stage.sh %q' \
  "$runner_workdir" microsoft_foundry_skill "$release_id" "$environment" "$expected_commit" "$stage"

az vm run-command invoke \
  --subscription "$subscription_id" \
  --resource-group "$runner_group" \
  --name "$runner_name" \
  --command-id RunShellScript \
  --scripts "$remote_command" \
  --output json |
  python3 "$SCRIPT_DIR/runner_manual_result.py" \
    --release-id "$release_id" \
    --stage "$stage"
