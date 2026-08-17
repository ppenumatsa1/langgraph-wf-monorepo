#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s <profile-path>\n' "$0" >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
project_root="$(cd "$script_dir/.." && pwd -P)"
source "$script_dir/profile.sh"

deployment_profile_load "$1"
deployment_profile_validate
deployment_profile_export

project_dir="${AZD_PROJECT_DIR:-$project_root/infra/foundry-hosted}"
project_dir="$(cd "$project_dir" && pwd -P)"
[[ "$project_dir" == "$project_root/"* ]] || {
  printf 'deployment profile error: AZD_PROJECT_DIR must stay inside this project\n' >&2
  exit 1
}
[[ -f "$project_dir/azure.yaml" ]] || {
  printf 'deployment profile error: no azure.yaml at %s\n' "$project_dir" >&2
  exit 1
}

azd_command="${AZD_COMMAND:-azd}"
command -v "$azd_command" >/dev/null 2>&1 || {
  printf 'deployment profile error: azd is required\n' >&2
  exit 1
}

(
  cd "$project_dir"
  if [[ -f ".azure/$AZURE_ENV_NAME/.env" ]]; then
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill "$azd_command" env select "$AZURE_ENV_NAME"
  else
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill "$azd_command" env new "$AZURE_ENV_NAME" --no-prompt
  fi

  for key in "${!DEPLOYMENT_PROFILE_VALUES[@]}"; do
    case "$key" in
      CONTRACT_VERSION|DEPLOYMENT_LANE|AZURE_ENV_NAME) continue ;;
    esac
    AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
      "$azd_command" env set "$key" "${DEPLOYMENT_PROFILE_VALUES[$key]}"
  done
)

printf 'Applied %s target profile to %s.\n' "$DEPLOYMENT_LANE" "$AZURE_ENV_NAME"
