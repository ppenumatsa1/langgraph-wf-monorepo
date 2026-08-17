#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CREDENTIAL_HELPER="$SCRIPT_DIR/postgres_runtime_credentials.py"

require_bin() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required binary: $1" >&2
    exit 1
  }
}

get_env() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env get-value "$1" --cwd "$FOUNDRY_DIR" --no-prompt 2>/dev/null || true
}

required_env() {
  local name="$1"
  local value
  value="$(get_env "$name")"
  if [[ -z "$value" ]]; then
    echo "Missing AZD environment value: $name" >&2
    exit 1
  fi
  printf '%s' "$value"
}

secure_value() {
  local name="$1"
  local value="${!name:-}"

  if [[ -z "$value" ]]; then
    value="$(get_env "$name")"
  fi
  if [[ -z "$value" && -t 0 ]]; then
    read -r -s -p "Enter ${name}: " value
    printf '\n' >&2
  fi
  if [[ -z "$value" ]]; then
    echo "${name} must be supplied through the local AZD environment, process environment, or secure terminal input." >&2
    exit 1
  fi
  if [[ "$value" == *$'\n'* || "$value" == *$'\r'* ]]; then
    echo "${name} must be a single-line value." >&2
    exit 1
  fi
  printf '%s' "$value"
}

require_identifier() {
  local name="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]]; then
    echo "${name} must be a PostgreSQL identifier up to 63 characters." >&2
    exit 1
  fi
}

require_password() {
  local name="$1"
  local value="$2"

  if (( ${#value} < 8 || ${#value} > 128 )); then
    echo "${name} must contain between 8 and 128 characters." >&2
    exit 1
  fi
}

set_azd_secret() {
  if ! AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env set "$1" "$2" --cwd "$FOUNDRY_DIR" --no-prompt >/dev/null 2>&1; then
    echo "Unable to save the local AZD environment credential." >&2
    exit 1
  fi
}

require_bin az
require_bin azd
require_bin python3
require_bin psql
[[ -r "$CREDENTIAL_HELPER" ]] || {
  echo "Missing PostgreSQL credential helper." >&2
  exit 1
}

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
server_name="$(required_env POSTGRES_SERVER_NAME)"
database_name="$(required_env POSTGRES_DATABASE)"
runtime_username="$(required_env POSTGRES_RUNTIME_USERNAME)"
admin_username="$(required_env POSTGRES_ADMIN_USERNAME)"
admin_password="$(secure_value POSTGRES_ADMIN_PASSWORD)"
hosted_password="$(secure_value POSTGRES_HOSTED_PASSWORD)"

require_identifier POSTGRES_DATABASE "$database_name"
require_identifier POSTGRES_RUNTIME_USERNAME "$runtime_username"
require_password POSTGRES_HOSTED_PASSWORD "$hosted_password"

az account set --subscription "$subscription_id" >/dev/null

password_auth="$(
  az postgres flexible-server show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$server_name" \
    --query 'authConfig.passwordAuth' \
    --output tsv
)"
active_directory_auth="$(
  az postgres flexible-server show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$server_name" \
    --query 'authConfig.activeDirectoryAuth' \
    --output tsv
)"
server_fqdn="$(
  az postgres flexible-server show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$server_name" \
    --query fullyQualifiedDomainName \
    --output tsv
)"
expected_server_fqdn="${server_name}.postgres.database.azure.com"

if [[ "$password_auth" != "Enabled" || "$active_directory_auth" != "Enabled" ]]; then
  echo "PostgreSQL authentication is not in the approved dual-authentication state; run make foundry-provision first." >&2
  exit 1
fi
if [[ "$server_fqdn" != "$expected_server_fqdn" ]]; then
  echo "PostgreSQL server did not return the expected Azure Database for PostgreSQL hostname." >&2
  exit 1
fi

firewall_start="$(
  az postgres flexible-server firewall-rule show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --server-name "$server_name" \
    --name allow-all-temporary \
    --query startIpAddress \
    --output tsv
)"
firewall_end="$(
  az postgres flexible-server firewall-rule show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --server-name "$server_name" \
    --name allow-all-temporary \
    --query endIpAddress \
    --output tsv
)"
if [[ "$firewall_start" != "0.0.0.0" || "$firewall_end" != "0.0.0.0" ]]; then
  echo "PostgreSQL firewall is not restricted to Azure services; run make foundry-provision first." >&2
  exit 1
fi

if ! az postgres flexible-server db show \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --server-name "$server_name" \
  --name "$database_name" \
  --output none >/dev/null 2>&1; then
  echo "PostgreSQL runtime database is absent; run make foundry-provision first." >&2
  exit 1
fi

bash "$SCRIPT_DIR/bootstrap_postgres_schema.sh"

scratch_dir="$ROOT_DIR/backend/.tmp/foundry"
run_stamp="$(date -u +%Y%m%d%H%M%S)-$$"
provision_file="$scratch_dir/provision-postgres-runtime-${run_stamp}.sql"
verification_file="$scratch_dir/verify-postgres-runtime-${run_stamp}.sql"
mkdir -p "$scratch_dir"
trap 'rm -f "$provision_file" "$verification_file"' EXIT
umask 077
(
  POSTGRES_DATABASE="$database_name" \
  POSTGRES_RUNTIME_USERNAME="$runtime_username" \
  POSTGRES_HOSTED_PASSWORD="$hosted_password" \
  POSTGRES_ADMIN_USERNAME="$admin_username" \
    python3 "$CREDENTIAL_HELPER" provision
) >"$provision_file"

if ! PGPASSWORD="$admin_password" PGSSLMODE=require \
  psql --host "$server_fqdn" \
    --username "$admin_username" \
    --dbname "$database_name" \
    --set ON_ERROR_STOP=on \
    --quiet \
    --file "$provision_file" >/dev/null 2>&1; then
  echo "PostgreSQL runtime credential provisioning failed; command output was withheld to protect credentials." >&2
  exit 1
fi

runtime_database_url="$(
  POSTGRES_DATABASE="$database_name" \
  POSTGRES_RUNTIME_USERNAME="$runtime_username" \
  POSTGRES_HOSTED_PASSWORD="$hosted_password" \
  POSTGRES_SERVER_FQDN="$server_fqdn" \
    python3 "$CREDENTIAL_HELPER" runtime-url
)"

(
  POSTGRES_DATABASE="$database_name" \
  POSTGRES_RUNTIME_USERNAME="$runtime_username" \
    python3 "$CREDENTIAL_HELPER" verify
) >"$verification_file"

if ! PGPASSWORD="$hosted_password" PGSSLMODE=require \
  psql --host "$server_fqdn" \
    --username "$runtime_username" \
    --dbname "$database_name" \
    --set ON_ERROR_STOP=on \
    --quiet \
    --file "$verification_file" >/dev/null 2>&1; then
  echo "PostgreSQL runtime credential verification failed; command output was withheld to protect credentials." >&2
  exit 1
fi

set_azd_secret RUNTIME_DATABASE_URL "$runtime_database_url"
set_azd_secret DATABASE_URL "$runtime_database_url"
set_azd_secret DB_AUTH_MODE password
set_azd_secret POSTGRES_HOSTED_PASSWORD "$hosted_password"

unset admin_password hosted_password runtime_database_url
echo "Provisioned or rotated the least-privilege PostgreSQL runtime credential in the local AZD environment."
