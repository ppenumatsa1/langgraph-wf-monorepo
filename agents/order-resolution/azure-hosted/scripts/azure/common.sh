#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
AZD_ROOT="$ROOT_DIR"
EXPECTED_SUBSCRIPTION_ID="7df95e88-701c-4693-af77-3159f83b558d"
EXPECTED_RESOURCE_GROUP="rg-langgraph-ora-azure-hosted"
EXPECTED_LOCATION="eastus2"

azd_value() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$AZD_ROOT" --no-prompt 2>/dev/null || true
}

required_azd_value() {
  local value
  value="$(azd_value "$1")"
  [[ -n "$value" ]] || {
    printf 'Missing AZD environment value: %s\n' "$1" >&2
    return 1
  }
  printf '%s' "$value"
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'Missing required command: %s\n' "$1" >&2
    return 1
  }
}

assert_target() {
  local subscription_id resource_group location
  subscription_id="$(required_azd_value AZURE_SUBSCRIPTION_ID)"
  resource_group="$(required_azd_value AZURE_RESOURCE_GROUP)"
  location="$(required_azd_value AZURE_LOCATION)"
  [[ "$subscription_id" == "$EXPECTED_SUBSCRIPTION_ID" ]] || {
    echo "Refusing non-canonical subscription: $subscription_id" >&2
    return 1
  }
  [[ "$resource_group" == "$EXPECTED_RESOURCE_GROUP" ]] || {
    echo "Refusing non-canonical resource group: $resource_group" >&2
    return 1
  }
  [[ "${location,,}" == "$EXPECTED_LOCATION" ]] || {
    echo "Refusing non-canonical location: $location" >&2
    return 1
  }
}

release_evidence_dir() {
  local release_id="${AZURE_RELEASE_ID:?AZURE_RELEASE_ID is required}"
  printf '%s/.artifacts/releases/%s/evidence' "$ROOT_DIR" "$release_id"
}
