#!/usr/bin/env bash
set -euo pipefail

PRIVATE_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PRIVATE_ROOT_DIR="$(cd "$PRIVATE_SCRIPT_DIR/../.." && pwd -P)"
PRIVATE_AZD_DIR="${FOUNDRY_PRIVATE_AZD_DIR:-$PRIVATE_ROOT_DIR/infra/foundry-hosted}"
PRIVATE_EXPECTED_SUBSCRIPTION_ID="7df95e88-701c-4693-af77-3159f83b558d"
PRIVATE_EXPECTED_RESOURCE_GROUP="rg-langgraph-ora-foundry-private"
PRIVATE_EXPECTED_LOCATION="eastus2"
PRIVATE_EXPECTED_ENVIRONMENT="order-resolution-foundry-private"
PRIVATE_RUNNER_WORKDIR_DEFAULT="/opt/order-resolution/source/agents/order-resolution/foundry-private"

private_die() {
  printf 'foundry-private: %s\n' "$*" >&2
  exit 1
}

private_require_command() {
  command -v "$1" >/dev/null 2>&1 ||
    private_die "missing required command: $1"
}

private_require_file() {
  [[ -f "$1" && ! -L "$1" ]] ||
    private_die "required regular file is missing: $1"
}

private_require_directory() {
  [[ -d "$1" && ! -L "$1" ]] ||
    private_die "required directory is missing: $1"
}

private_azd() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd "$@"
}

private_azd_value() {
  local key="$1"
  local value
  private_require_file "$PRIVATE_AZD_DIR/azure.yaml"
  if ! value="$(private_azd env get-value "$key" --cwd "$PRIVATE_AZD_DIR" --no-prompt)"; then
    private_die "unable to read AZD environment value: $key"
  fi
  [[ -n "$value" ]] || private_die "AZD environment value is required: $key"
  printf '%s' "$value"
}

private_azd_set() {
  local key="$1"
  local value="$2"
  private_azd env set "$key" "$value" --cwd "$PRIVATE_AZD_DIR" --no-prompt >/dev/null
}

private_azd_optional_value() {
  local key="$1"
  local value
  private_require_file "$PRIVATE_AZD_DIR/azure.yaml"
  if ! value="$(private_azd env get-value "$key" --cwd "$PRIVATE_AZD_DIR" --no-prompt 2>/dev/null)"; then
    return 1
  fi
  [[ -n "$value" ]] || return 1
  printf '%s' "$value"
}

private_require_target() {
  local subscription_id resource_group location environment
  subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
  resource_group="$(private_azd_value AZURE_RESOURCE_GROUP)"
  location="$(private_azd_value AZURE_LOCATION)"
  environment="$(private_azd_value AZURE_ENV_NAME)"

  [[ "$subscription_id" == "$PRIVATE_EXPECTED_SUBSCRIPTION_ID" ]] ||
    private_die "refusing unexpected subscription: $subscription_id"
  [[ "$resource_group" == "$PRIVATE_EXPECTED_RESOURCE_GROUP" ]] ||
    private_die "refusing unexpected resource group: $resource_group"
  [[ "${location,,}" == "$PRIVATE_EXPECTED_LOCATION" ]] ||
    private_die "refusing unexpected location: $location"
  [[ "$environment" == "$PRIVATE_EXPECTED_ENVIRONMENT" ]] ||
    private_die "refusing unexpected AZD environment: $environment"
}

private_release_id() {
  local release_id="${FOUNDRY_PRIVATE_RELEASE_ID:-}"
  [[ "$release_id" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$ ]] ||
    private_die "FOUNDRY_PRIVATE_RELEASE_ID must satisfy the release identifier contract"
  printf '%s' "$release_id"
}

private_release_dir() {
  printf '%s/.artifacts/releases/%s' "$PRIVATE_ROOT_DIR" "$(private_release_id)"
}

private_required_env_value() {
  local key="$1"
  local value
  value="$(private_azd_value "$key")"
  [[ -n "$value" ]] || private_die "required AZD value is missing: $key"
  printf '%s' "$value"
}

private_validate_identifier() {
  local name="$1"
  local value="$2"
  [[ "$value" =~ ^[A-Za-z0-9][A-Za-z0-9._/-]{0,255}$ ]] ||
    private_die "$name contains unsupported characters"
}

private_validate_absolute_path() {
  local name="$1"
  local value="$2"
  [[ "$value" =~ ^/[A-Za-z0-9._/-]+$ && "$value" != *".."* ]] ||
    private_die "$name must be an absolute, traversal-free path"
}

private_runner_resource_group() {
  # The runner VM is deliberately colocated with the private lane resources.
  printf '%s' "$PRIVATE_EXPECTED_RESOURCE_GROUP"
}

private_runner_name() {
  local value
  value="$(private_required_env_value PRIVATE_RUNNER_VM_NAME)"
  private_validate_identifier PRIVATE_RUNNER_VM_NAME "$value"
  printf '%s' "$value"
}

private_runner_workdir() {
  local value="${FOUNDRY_PRIVATE_RUNNER_WORKDIR:-}"
  if [[ -z "$value" ]]; then
    value="$(private_azd_optional_value PRIVATE_RUNNER_WORKDIR || true)"
  fi
  value="${value:-$PRIVATE_RUNNER_WORKDIR_DEFAULT}"
  private_validate_absolute_path PRIVATE_RUNNER_WORKDIR "$value"
  printf '%s' "$value"
}

private_assert_clean_source() {
  private_require_command git
  git -C "$PRIVATE_ROOT_DIR" diff --quiet ||
    private_die "refusing release from a worktree with unstaged changes"
  git -C "$PRIVATE_ROOT_DIR" diff --cached --quiet ||
    private_die "refusing release from a worktree with staged changes"
  git -C "$PRIVATE_ROOT_DIR" rev-parse --verify HEAD >/dev/null ||
    private_die "the release source must have a committed HEAD"
  [[ -z "$(git -C "$PRIVATE_ROOT_DIR" status --porcelain --untracked-files=normal -- .)" ]] ||
    private_die "refusing release from a worktree with untracked source files"
}
