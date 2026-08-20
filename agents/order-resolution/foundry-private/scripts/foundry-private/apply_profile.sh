#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

profile_path="${FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE:-}"
[[ -n "$profile_path" ]] ||
  private_die "FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE is required"
private_require_command python3
private_require_command azd
private_require_file "$profile_path"

profile_json="$(python3 "$SCRIPT_DIR/profile_gate.py" --runtime --json "$profile_path")"
environment="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["AZURE_ENV_NAME"])' <<<"$profile_json")"

if [[ -d "$PRIVATE_AZD_DIR/.azure/$environment" ]]; then
  private_azd env select "$environment" --cwd "$PRIVATE_AZD_DIR" --no-prompt
else
  private_azd env new "$environment" --cwd "$PRIVATE_AZD_DIR" --no-prompt
fi

while IFS=$'\t' read -r key value; do
  private_azd env set "$key" "$value" --cwd "$PRIVATE_AZD_DIR" --no-prompt >/dev/null
done < <(
  python3 -c '
import json
import sys
for key, value in sorted(json.load(sys.stdin).items()):
    print(f"{key}\t{value}")
' <<<"$profile_json"
)

private_require_target
printf 'Applied secret-free foundry-private profile to %s.\n' "$environment"
