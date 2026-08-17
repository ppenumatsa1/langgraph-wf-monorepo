#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR"
SCHEMA_FILE="$ROOT_DIR/backend/app/sql/schema.sql"

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

for command in az azd psql python3; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "Missing required binary: $command" >&2
    exit 1
  }
done
[[ -r "$SCHEMA_FILE" ]] || {
  echo "Missing canonical PostgreSQL schema." >&2
  exit 1
}

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
server_name="$(required_env POSTGRES_SERVER_NAME)"
database_name="$(required_env POSTGRES_DATABASE)"
admin_username="$(required_env POSTGRES_ADMIN_PRINCIPAL_NAME)"
admin_token="$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)"
python_bin="$ROOT_DIR/backend/.venv/bin/python"
[[ -x "$python_bin" ]] || python_bin=python3

az account set --subscription "$subscription_id" >/dev/null
if ! PGPASSWORD="$admin_token" PGSSLMODE=require \
  psql --host "${server_name}.postgres.database.azure.com" \
    --username "$admin_username" \
    --dbname "$database_name" \
    --set ON_ERROR_STOP=on \
    --quiet \
    --file "$SCHEMA_FILE" >/dev/null 2>&1; then
  echo "PostgreSQL schema bootstrap failed; command output was withheld to protect credentials." >&2
  exit 1
fi

unset admin_token
admin_database_url="$(
  POSTGRES_SERVER_NAME="$server_name" \
  POSTGRES_DATABASE="$database_name" \
  POSTGRES_ADMIN_USERNAME="$admin_username" \
  POSTGRES_ADMIN_PASSWORD="$(az account get-access-token --resource-type oss-rdbms --query accessToken -o tsv)" \
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
  "$python_bin" - <<'PY' >/dev/null 2>&1
import asyncio
import os

from app.langgraph.checkpointer import PostgresCheckpointerFactory

asyncio.run(PostgresCheckpointerFactory(os.environ["DATABASE_URL"]).setup())
PY
then
  echo "LangGraph checkpoint schema bootstrap failed; command output was withheld to protect credentials." >&2
  exit 1
fi

unset admin_database_url
echo "Bootstrapped the order-resolution application and LangGraph checkpoint schemas."
