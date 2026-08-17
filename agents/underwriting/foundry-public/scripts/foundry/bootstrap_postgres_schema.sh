#!/usr/bin/env bash
set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
readonly FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"
readonly PYTHON="$ROOT_DIR/.venv/bin/python"
readonly DDL_GENERATOR="$ROOT_DIR/scripts/foundry/generate_postgres_schema_ddl.py"

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

require_bin az
require_bin azd
require_bin psql
[[ -x "$PYTHON" ]] || {
  echo "Missing project virtual environment; run make install first." >&2
  exit 1
}
[[ -r "$DDL_GENERATOR" ]] || {
  echo "Missing PostgreSQL schema DDL generator." >&2
  exit 1
}

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
server_name="$(required_env POSTGRES_SERVER_NAME)"
database_name="$(required_env POSTGRES_DATABASE)"
admin_username="$(required_env POSTGRES_ADMIN_USERNAME)"
admin_password="$(required_env POSTGRES_ADMIN_PASSWORD)"

az account set --subscription "$subscription_id" >/dev/null
scratch_dir="$ROOT_DIR/backend/.tmp/foundry"
run_stamp="$(date -u +%Y%m%d%H%M%S)-$$"
schema_file="$scratch_dir/bootstrap-postgres-schema-${run_stamp}.sql"
mkdir -p "$scratch_dir"
trap 'rm -f "$schema_file"' EXIT
umask 077
PYTHONPATH="$ROOT_DIR/backend" "$PYTHON" "$DDL_GENERATOR" >"$schema_file"

if ! PGPASSWORD="$admin_password" PGSSLMODE=require \
  psql --host "${server_name}.postgres.database.azure.com" \
    --username "$admin_username" \
    --dbname "$database_name" \
    --set ON_ERROR_STOP=on \
    --quiet \
    --file "$schema_file" >/dev/null 2>&1; then
  echo "PostgreSQL schema bootstrap failed; command output was withheld to protect credentials." >&2
  exit 1
fi

admin_database_url="$(
  POSTGRES_SERVER_NAME="$server_name" \
  POSTGRES_DATABASE="$database_name" \
  POSTGRES_ADMIN_USERNAME="$admin_username" \
  POSTGRES_ADMIN_PASSWORD="$admin_password" \
    python3 - <<'PY'
import os
from urllib.parse import quote

username = quote(os.environ["POSTGRES_ADMIN_USERNAME"], safe="")
password = quote(os.environ["POSTGRES_ADMIN_PASSWORD"], safe="")
server = os.environ["POSTGRES_SERVER_NAME"]
database = quote(os.environ["POSTGRES_DATABASE"], safe="")
print(
    f"postgresql://{username}:{password}@"
    f"{server}.postgres.database.azure.com:5432/{database}?sslmode=require"
)
PY
)"
if ! PYTHONPATH="$ROOT_DIR/backend" \
  DATABASE_URL="$admin_database_url" \
  LANGGRAPH_STRICT_MSGPACK=true \
  "$PYTHON" -m app.sql.bootstrap >/dev/null 2>&1
then
  echo "LangGraph checkpoint schema bootstrap failed; command output was withheld to protect credentials." >&2
  exit 1
fi

unset admin_password admin_database_url
printf 'Verified PostgreSQL resource group: %s\n' "$resource_group" >/dev/null
echo "Bootstrapped the underwriting application and LangGraph checkpoint schemas."
