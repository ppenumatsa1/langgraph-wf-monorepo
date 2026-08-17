#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

for command in az azd curl docker jq python3; do
  require_command "$command"
done

"$SCRIPT_DIR/ensure_azd_defaults.sh"
assert_target

subscription_id="$(required_azd_value AZURE_SUBSCRIPTION_ID)"
az account show --query id -o tsv | grep -Fxq "$subscription_id" || {
  echo "Azure CLI is not authenticated to the target subscription." >&2
  exit 1
}

echo "Azure-hosted preflight passed for ${EXPECTED_SUBSCRIPTION_ID}/${EXPECTED_RESOURCE_GROUP}."
