#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CREDENTIAL_HELPER="$SCRIPT_DIR/postgres_runtime_credentials.py"

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
  [[ -n "$value" ]] || value="$(get_env "$name")"
  if [[ -z "$value" && -t 0 ]]; then
    read -r -s -p "Enter ${name}: " value
    printf '\n' >&2
  fi
  if [[ -z "$value" || "$value" == *$'\n'* || "$value" == *$'\r'* ]]; then
    echo "${name} must be a non-empty single-line secret." >&2
    exit 1
  fi
  printf '%s' "$value"
}

set_secret() {
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env set "$1" "$2" --cwd "$FOUNDRY_DIR" --no-prompt >/dev/null 2>&1 || {
      echo "Unable to save the local AZD credential." >&2
      exit 1
    }
}

for command in az azd python3 psql; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required binary: $command" >&2
    exit 1
  }
done

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
server_name="$(required_env POSTGRES_SERVER_NAME)"
database_name="$(required_env POSTGRES_DATABASE)"
runtime_username="$(required_env POSTGRES_RUNTIME_USERNAME)"
admin_username="$(required_env POSTGRES_ADMIN_PRINCIPAL_NAME)"
admin_password="$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)"
runtime_password="$(secure_value POSTGRES_RUNTIME_PASSWORD)"

[[ "$database_name" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]] || {
  echo "POSTGRES_DATABASE is not a valid identifier." >&2
  exit 1
}
[[ "$runtime_username" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]] || {
  echo "POSTGRES_RUNTIME_USERNAME is not a valid identifier." >&2
  exit 1
}
(( ${#runtime_password} >= 8 && ${#runtime_password} <= 128 )) || {
  echo "POSTGRES_RUNTIME_PASSWORD must contain 8-128 characters." >&2
  exit 1
}

az account set --subscription "$subscription_id" >/dev/null
server_fqdn="$(az postgres flexible-server show --subscription "$subscription_id" --resource-group "$resource_group" --name "$server_name" --query fullyQualifiedDomainName -o tsv)"
[[ "$server_fqdn" == "${server_name}.postgres.database.azure.com" ]] || {
  echo "PostgreSQL returned an unexpected hostname." >&2
  exit 1
}

bash "$SCRIPT_DIR/bootstrap_postgres_schema.sh"

scratch_dir="$ROOT_DIR/backend/.tmp/foundry"
run_stamp="$(date -u +%Y%m%d%H%M%S)-$$"
provision_file="$scratch_dir/provision-runtime-${run_stamp}.sql"
verification_file="$scratch_dir/verify-runtime-${run_stamp}.sql"
mkdir -p "$scratch_dir"
trap 'rm -f "$provision_file" "$verification_file"' EXIT
umask 077

POSTGRES_DATABASE="$database_name" \
POSTGRES_RUNTIME_USERNAME="$runtime_username" \
POSTGRES_RUNTIME_PASSWORD="$runtime_password" \
POSTGRES_ADMIN_USERNAME="$admin_username" \
  python3 "$CREDENTIAL_HELPER" provision >"$provision_file"

if ! PGPASSWORD="$admin_password" PGSSLMODE=require \
  psql --host "$server_fqdn" --username "$admin_username" --dbname "$database_name" \
    --set ON_ERROR_STOP=on --quiet --file "$provision_file" >/dev/null 2>&1; then
  echo "Runtime credential provisioning failed; output was withheld." >&2
  exit 1
fi

runtime_database_url="$(
  POSTGRES_DATABASE="$database_name" \
  POSTGRES_RUNTIME_USERNAME="$runtime_username" \
  POSTGRES_RUNTIME_PASSWORD="$runtime_password" \
  POSTGRES_SERVER_FQDN="$server_fqdn" \
    python3 "$CREDENTIAL_HELPER" runtime-url
)"
POSTGRES_DATABASE="$database_name" POSTGRES_RUNTIME_USERNAME="$runtime_username" \
  python3 "$CREDENTIAL_HELPER" verify >"$verification_file"

if ! PGPASSWORD="$runtime_password" PGSSLMODE=require \
  psql --host "$server_fqdn" --username "$runtime_username" --dbname "$database_name" \
    --set ON_ERROR_STOP=on --quiet --file "$verification_file" >/dev/null 2>&1; then
  echo "Runtime credential verification failed; output was withheld." >&2
  exit 1
fi

set_secret RUNTIME_DATABASE_URL "$runtime_database_url"
set_secret DATABASE_URL "$runtime_database_url"
set_secret DB_AUTH_MODE password
set_secret POSTGRES_RUNTIME_PASSWORD "$runtime_password"
unset admin_password runtime_password runtime_database_url
echo "Provisioned or rotated the least-privilege PostgreSQL runtime credential."
