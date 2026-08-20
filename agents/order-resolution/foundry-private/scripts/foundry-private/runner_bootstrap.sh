#!/usr/bin/env bash
set -euo pipefail
set +x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

for command in az azd base64 gh git jq; do
  private_require_command "$command"
done
private_require_target
private_assert_clean_source
private_require_file "$SCRIPT_DIR/runner_bootstrap_remote.sh"

subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
location="$(private_azd_value AZURE_LOCATION)"
environment="$(private_azd_value AZURE_ENV_NAME)"
runner_group="$(private_runner_resource_group)"
runner_name="$(private_runner_name)"
runner_workdir="$(private_runner_workdir)"
repository_url="$(private_required_env_value PRIVATE_SOURCE_REPOSITORY_URL)"
expected_commit="$(git -C "$PRIVATE_ROOT_DIR" rev-parse HEAD)"
release_id="$(private_release_id)"
command_name="private-runner-bootstrap"
request_file="/dev/shm/foundry-private-run-command-$$.json"
vm_id="/subscriptions/$subscription_id/resourceGroups/$runner_group/providers/Microsoft.Compute/virtualMachines/$runner_name"

[[ "$repository_url" =~ ^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\.git$ ]] ||
  private_die "PRIVATE_SOURCE_REPOSITORY_URL must be an approved HTTPS GitHub repository"
[[ "$runner_workdir" == "/opt/order-resolution/source/agents/order-resolution/foundry-private" ]] ||
  private_die "private runner workdir does not match the approved source root"

repository_slug="${repository_url#https://github.com/}"
repository_slug="${repository_slug%.git}"
remote_commit="$(
  gh api \
    -H "Accept: application/vnd.github+json" \
    "repos/$repository_slug/commits/$expected_commit" \
    --jq '.sha' 2>/dev/null || true
)"
[[ "$remote_commit" == "$expected_commit" ]] ||
  private_die "release commit must be pushed to the private source repository before runner bootstrap"

token="$(gh auth token)"
[[ -n "$token" ]] || private_die "GitHub authentication token is unavailable"
azd_env_b64="$(
  private_azd env get-values --cwd "$PRIVATE_AZD_DIR" --no-prompt |
    base64 -w0
)"
[[ -n "$azd_env_b64" ]] || private_die "local AZD environment export is empty"

cleanup_command() {
  unset token azd_env_b64
  rm -f -- "$request_file"
  az vm run-command delete \
    --subscription "$subscription_id" \
    --resource-group "$runner_group" \
    --vm-name "$runner_name" \
    --run-command-name "$command_name" \
    --yes \
    --output none >/dev/null 2>&1 || true
}
trap cleanup_command EXIT
umask 077
jq -n \
  --rawfile script "$SCRIPT_DIR/runner_bootstrap_remote.sh" \
  --arg location "$location" \
  --arg expectedCommit "$expected_commit" \
  --arg repositoryUrl "$repository_url" \
  --arg workdir "$runner_workdir" \
  --arg environment "$environment" \
  --arg subscriptionId "$subscription_id" \
  --arg token "$token" \
  --arg azdEnv "$azd_env_b64" \
  '{
    location: $location,
    properties: {
      source: {script: $script},
      asyncExecution: true,
      timeoutInSeconds: 3600,
      parameters: [
        {name: "EXPECTED_COMMIT", value: $expectedCommit},
        {name: "REPOSITORY_URL", value: $repositoryUrl},
        {name: "WORKDIR", value: $workdir},
        {name: "AZD_ENV_NAME", value: $environment},
        {name: "AZURE_SUBSCRIPTION_ID", value: $subscriptionId},
        {name: "AZURE_LOCATION", value: $location}
      ],
      protectedParameters: [
        {name: "GITHUB_TOKEN", value: $token},
        {name: "AZD_ENV_B64", value: $azdEnv}
      ]
    }
  }' >"$request_file"

az rest \
  --method put \
  --url "https://management.azure.com${vm_id}/runCommands/${command_name}?api-version=2024-11-01" \
  --body "@$request_file" \
  --output none
unset token azd_env_b64

result=""
for _ in $(seq 1 240); do
  result="$(
    az vm run-command show \
      --subscription "$subscription_id" \
      --resource-group "$runner_group" \
      --vm-name "$runner_name" \
      --run-command-name "$command_name" \
      --instance-view \
      --output json
  )"
  execution_state="$(jq -r '.instanceView.executionState // empty' <<<"$result")"
  case "$execution_state" in
    Succeeded|Failed) break ;;
  esac
  sleep 15
done
execution_state="$(jq -r '.instanceView.executionState // empty' <<<"$result")"
exit_code="$(jq -r '.instanceView.exitCode // empty' <<<"$result")"
[[ "$execution_state" == "Succeeded" && "$exit_code" == "0" ]] || {
  jq -r '.instanceView.error // "private runner bootstrap failed"' <<<"$result" >&2
  exit 1
}
output="$(jq -r '.instanceView.output // empty' <<<"$result")"
details="$(sed -n '/^{/,$p' <<<"$output" | tail -n 1)"
jq -e \
  --arg commit "$expected_commit" \
  '.status == "passed" and .source_commit == $commit' \
  <<<"$details" >/dev/null ||
  private_die "private runner bootstrap returned invalid evidence"

cleanup_command
trap - EXIT

jq -n \
  --arg release_id "$release_id" \
  --arg commit "$expected_commit" \
  --arg repository "$repository_url" \
  --arg workdir "$runner_workdir" \
  --argjson runtime "$details" \
  '{release_id:$release_id,source_commit:$commit,repository:$repository,workdir:$workdir,run_command_deleted:true,runtime:$runtime}'
