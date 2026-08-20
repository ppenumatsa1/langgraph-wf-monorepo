#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

if [[ $# -ne 2 ]]; then
  printf 'Usage: %s <stage> <release-evidence-relative-path>\n' "$0" >&2
  exit 2
fi

stage="$1"
relative_path="$2"
case "$stage" in
  runner_preflight|postgres_schema|postgres_credentials|postgres_readiness|acr_package|deploy_backend|deploy_frontend|deploy_hosted|verify_runtime|smoke|hosted_e2e|browser_e2e|evaluation|telemetry) ;;
  *) private_die "unsupported private runner stage: $stage" ;;
esac
[[ "$relative_path" =~ ^evidence/[A-Za-z0-9._/-]+\.json$ && "$relative_path" != *".."* ]] ||
  private_die "release evidence path must be a traversal-free evidence JSON path"

private_require_command az
private_require_command jq
private_require_command python3
private_require_target
private_assert_clean_source
release_id="$(private_release_id)"
subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
environment="$(private_azd_value AZURE_ENV_NAME)"
runner_group="$(private_runner_resource_group)"
runner_name="$(private_runner_name)"
runner_workdir="$(private_runner_workdir)"
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
  python3 "$SCRIPT_DIR/runner_result.py" \
    --release-id "$release_id" \
    --relative-path "$relative_path" \
    --stage "$stage"
