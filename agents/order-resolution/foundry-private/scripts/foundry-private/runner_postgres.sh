#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

stage="${1:-}"
case "$stage" in
  postgres_schema|postgres_credentials|postgres_readiness) ;;
  *) private_die "unsupported PostgreSQL runner stage" ;;
esac

for command in az jq psql python3; do
  private_require_command "$command"
done
private_require_target

python="$PRIVATE_ROOT_DIR/backend/.venv/bin/python"
schema_file="$PRIVATE_ROOT_DIR/backend/app/sql/schema.sql"
credential_helper="$SCRIPT_DIR/postgres_runtime_credentials.py"
connection_template="$PRIVATE_AZD_DIR/iac/modules/foundry-project-runtime-secret-connection.bicep"
private_require_file "$schema_file"
private_require_file "$credential_helper"
private_require_file "$connection_template"
[[ -x "$python" ]] ||
  private_die "private runner requires backend/.venv for PostgreSQL schema bootstrap"

sensitive_files=()
cleanup_sensitive_files() {
  local file
  for file in "${sensitive_files[@]}"; do
    rm -f -- "$file"
  done
}
trap cleanup_sensitive_files EXIT

subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(private_azd_value AZURE_RESOURCE_GROUP)"
server_name="$(private_required_env_value POSTGRES_SERVER_NAME)"
database_name="$(private_required_env_value POSTGRES_DATABASE)"
server_json="$(az postgres flexible-server show --subscription "$subscription_id" --resource-group "$resource_group" --name "$server_name" --output json)"
[[ "$(jq -r '.state // .properties.state // empty' <<<"$server_json")" == "Ready" ]] ||
  private_die "private PostgreSQL server is not Ready"
[[ "$(jq -r '.network.publicNetworkAccess // .properties.network.publicNetworkAccess // empty' <<<"$server_json")" == "Disabled" ]] ||
  private_die "private PostgreSQL server public network access must be Disabled"
server_fqdn="$(jq -r '.fullyQualifiedDomainName // .properties.fullyQualifiedDomainName // empty' <<<"$server_json")"
[[ "$server_fqdn" == "${server_name}.postgres.database.azure.com" ]] ||
  private_die "private PostgreSQL server returned an unexpected host name"

private_schema_bootstrap() {
  local admin_username admin_password admin_database_url
  admin_username="$(private_required_env_value POSTGRES_ADMIN_USERNAME)"
  admin_password="$(private_required_env_value POSTGRES_ADMIN_PASSWORD)"

  if ! PGPASSWORD="$admin_password" PGSSLMODE=require \
    psql --host "$server_fqdn" --username "$admin_username" --dbname "$database_name" \
      --set ON_ERROR_STOP=on --quiet --file "$schema_file" >/dev/null 2>&1; then
    unset admin_password
    private_die "private PostgreSQL application schema bootstrap failed"
  fi

  admin_database_url="$(
    POSTGRES_SERVER_FQDN="$server_fqdn" \
    POSTGRES_DATABASE="$database_name" \
    POSTGRES_ADMIN_USERNAME="$admin_username" \
    POSTGRES_ADMIN_PASSWORD="$admin_password" \
      python3 - <<'PY'
import os
from urllib.parse import quote

print(
    "postgresql://"
    f"{quote(os.environ['POSTGRES_ADMIN_USERNAME'], safe='')}:"
    f"{quote(os.environ['POSTGRES_ADMIN_PASSWORD'], safe='')}@"
    f"{os.environ['POSTGRES_SERVER_FQDN']}:5432/"
    f"{quote(os.environ['POSTGRES_DATABASE'], safe='')}?sslmode=require"
)
PY
  )"
  if ! PYTHONPATH="$PRIVATE_ROOT_DIR/backend" \
    DATABASE_URL="$admin_database_url" \
    LANGGRAPH_STRICT_MSGPACK=true \
    "$python" - <<'PY' >/dev/null 2>&1
import asyncio
import os

from app.langgraph.checkpointer import PostgresCheckpointerFactory

asyncio.run(PostgresCheckpointerFactory(os.environ["DATABASE_URL"]).setup())
PY
  then
    unset admin_password admin_database_url
    private_die "private LangGraph checkpoint schema bootstrap failed"
  fi
  unset admin_password admin_database_url
}

private_converge_runtime_connection() {
  local runtime_url="$1"
  local account_name project_name location connection_name
  local scratch_dir parameter_file deployment_name deployment_prefix connection_url metadata release_id release_slug

  account_name="$(private_required_env_value FOUNDRY_ACCOUNT_NAME)"
  project_name="$(private_required_env_value FOUNDRY_PROJECT_NAME)"
  location="$(private_azd_value AZURE_LOCATION)"
  if connection_name="$(private_azd_optional_value FOUNDRY_RUNTIME_CONNECTION_NAME)"; then
    [[ "$connection_name" == "orderresolutionprivateruntimesecrets" ]] ||
      private_die "unexpected private runtime connection name"
  else
    connection_name="orderresolutionprivateruntimesecrets"
    private_azd_set FOUNDRY_RUNTIME_CONNECTION_NAME "$connection_name"
  fi

  scratch_dir="$PRIVATE_ROOT_DIR/.artifacts/private-runner-postgres/$(private_release_id)"
  parameter_file="$scratch_dir/runtime-connection.json"
  mkdir -p "$scratch_dir"
  umask 077
  sensitive_files+=("$parameter_file")
  RUNTIME_CONNECTION_ACCOUNT_NAME="$account_name" \
  RUNTIME_CONNECTION_PROJECT_NAME="$project_name" \
  RUNTIME_CONNECTION_LOCATION="$location" \
  RUNTIME_CONNECTION_NAME="$connection_name" \
  RUNTIME_CONNECTION_DATABASE_URL="$runtime_url" \
    python3 - "$parameter_file" <<'PY'
import json
import os
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
            "contentVersion": "1.0.0.0",
            "parameters": {
                "accountName": {"value": os.environ["RUNTIME_CONNECTION_ACCOUNT_NAME"]},
                "projectName": {"value": os.environ["RUNTIME_CONNECTION_PROJECT_NAME"]},
                "location": {"value": os.environ["RUNTIME_CONNECTION_LOCATION"]},
                "runtimeConnectionName": {"value": os.environ["RUNTIME_CONNECTION_NAME"]},
                "runtimeDatabaseUrl": {"value": os.environ["RUNTIME_CONNECTION_DATABASE_URL"]},
            },
        }
    ),
    encoding="utf-8",
)
PY

  release_id="$(private_release_id)"
  release_slug="${release_id//[^A-Za-z0-9-]/-}"
  deployment_prefix="order-resolution-private-runtime-"
  deployment_name="${deployment_prefix}${release_slug:0:$((64 - ${#deployment_prefix}))}"
  if ! az deployment group create \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$deployment_name" \
    --template-file "$connection_template" \
    --parameters "@$parameter_file" \
    --only-show-errors \
    --output none; then
    rm -f -- "$parameter_file"
    private_die "private Foundry runtime connection deployment failed"
  fi
  rm -f -- "$parameter_file"

  connection_url="https://management.azure.com/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/${account_name}/projects/${project_name}/connections/${connection_name}?api-version=2025-04-01-preview"
  metadata="$(az rest --subscription "$subscription_id" --method get --url "$connection_url" --output json)"
  jq -e --arg name "$connection_name" \
    '.name == $name and .properties.category == "CustomKeys" and .properties.authType == "CustomKeys"' \
    <<<"$metadata" >/dev/null ||
    private_die "private Foundry runtime connection metadata is invalid"
}

private_credentials_bootstrap() {
  local admin_username admin_password runtime_username hosted_password runtime_url
  local scratch_dir provision_file verification_file

  admin_username="$(private_required_env_value POSTGRES_ADMIN_USERNAME)"
  admin_password="$(private_required_env_value POSTGRES_ADMIN_PASSWORD)"
  runtime_username="$(private_required_env_value POSTGRES_RUNTIME_USERNAME)"
  [[ "$database_name" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]] ||
    private_die "POSTGRES_DATABASE is not a valid identifier"
  [[ "$runtime_username" =~ ^[A-Za-z_][A-Za-z0-9_]{0,62}$ ]] ||
    private_die "POSTGRES_RUNTIME_USERNAME is not a valid identifier"

  if hosted_password="$(private_azd_optional_value POSTGRES_HOSTED_PASSWORD)"; then
    :
  else
    hosted_password="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  fi
  (( ${#hosted_password} >= 8 && ${#hosted_password} <= 128 )) ||
    private_die "POSTGRES_HOSTED_PASSWORD must contain 8-128 characters"

  scratch_dir="$PRIVATE_ROOT_DIR/.artifacts/private-runner-postgres/$(private_release_id)"
  provision_file="$scratch_dir/provision-runtime.sql"
  verification_file="$scratch_dir/verify-runtime.sql"
  mkdir -p "$scratch_dir"
  umask 077
  sensitive_files+=("$provision_file" "$verification_file")
  POSTGRES_DATABASE="$database_name" \
  POSTGRES_RUNTIME_USERNAME="$runtime_username" \
  POSTGRES_HOSTED_PASSWORD="$hosted_password" \
  POSTGRES_ADMIN_USERNAME="$admin_username" \
    python3 "$credential_helper" provision >"$provision_file"

  if ! PGPASSWORD="$admin_password" PGSSLMODE=require \
    psql --host "$server_fqdn" --username "$admin_username" --dbname "$database_name" \
      --set ON_ERROR_STOP=on --quiet --file "$provision_file" >/dev/null 2>&1; then
    rm -f -- "$provision_file" "$verification_file"
    unset admin_password hosted_password
    private_die "private PostgreSQL runtime credential provisioning failed"
  fi

  runtime_url="$(
    POSTGRES_DATABASE="$database_name" \
    POSTGRES_RUNTIME_USERNAME="$runtime_username" \
    POSTGRES_HOSTED_PASSWORD="$hosted_password" \
    POSTGRES_SERVER_FQDN="$server_fqdn" \
      python3 "$credential_helper" runtime-url
  )"
  POSTGRES_DATABASE="$database_name" \
  POSTGRES_RUNTIME_USERNAME="$runtime_username" \
    python3 "$credential_helper" verify >"$verification_file"
  if ! PGPASSWORD="$hosted_password" PGSSLMODE=require \
    psql --host "$server_fqdn" --username "$runtime_username" --dbname "$database_name" \
      --set ON_ERROR_STOP=on --quiet --file "$verification_file" >/dev/null 2>&1; then
    rm -f -- "$provision_file" "$verification_file"
    unset admin_password hosted_password runtime_url
    private_die "private PostgreSQL runtime credential verification failed"
  fi
  rm -f -- "$provision_file" "$verification_file"

  private_azd_set RUNTIME_DATABASE_URL "$runtime_url"
  private_azd_set DATABASE_URL "$runtime_url"
  private_azd_set DB_AUTH_MODE password
  private_azd_set POSTGRES_HOSTED_PASSWORD "$hosted_password"
  private_converge_runtime_connection "$runtime_url"
  install -d -m 700 /var/lib/order-resolution
  install -m 600 \
    "$PRIVATE_AZD_DIR/.azure/$PRIVATE_EXPECTED_ENVIRONMENT/.env" \
    /var/lib/order-resolution/private-runner.env
  unset admin_password hosted_password runtime_url
}

private_readiness_check() {
  local runtime_url runtime_username
  runtime_url="$(private_required_env_value RUNTIME_DATABASE_URL)"
  runtime_username="$(private_required_env_value POSTGRES_RUNTIME_USERNAME)"
  [[ "$runtime_url" == postgresql+psycopg://* &&
    "$runtime_url" == *"${server_fqdn}"* &&
    "$runtime_url" == *"sslmode=require"* ]] ||
    private_die "private runtime PostgreSQL URL must use TLS and the expected host"
  PGPASSWORD="$(private_required_env_value POSTGRES_HOSTED_PASSWORD)" \
    PGSSLMODE=require \
    psql --host "$server_fqdn" --username "$runtime_username" --dbname "$database_name" \
      --set ON_ERROR_STOP=on --quiet \
      --command 'SELECT 1 FROM public.workflow_runs LIMIT 1;' >/dev/null
}

case "$stage" in
  postgres_schema) private_schema_bootstrap ;;
  postgres_credentials) private_credentials_bootstrap ;;
  postgres_readiness) private_readiness_check ;;
esac

jq -n --arg database "$database_name" --arg stage "$stage" \
  '{stage:$stage,database:$database,private_network:true,tls_required:true,schema_managed_externally:true}'
