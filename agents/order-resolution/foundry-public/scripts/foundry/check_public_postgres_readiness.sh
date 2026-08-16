#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FOUNDRY_DIR="$ROOT_DIR/infra/foundry-hosted"

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

subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_env AZURE_RESOURCE_GROUP)"
server_name="$(required_env POSTGRES_SERVER_NAME)"
database_name="$(required_env POSTGRES_DATABASE)"
runtime_username="$(required_env POSTGRES_RUNTIME_USERNAME)"
hosted_password="$(required_env POSTGRES_HOSTED_PASSWORD)"
operator_ip="$(required_env POSTGRES_OPERATOR_IP)"
database_url="$(required_env DATABASE_URL)"
runtime_database_url="$(required_env RUNTIME_DATABASE_URL)"
db_auth_mode="$(required_env DB_AUTH_MODE)"

[[ "$db_auth_mode" == "password" ]] || {
  echo "DB_AUTH_MODE must be password." >&2
  exit 1
}
[[ "$database_url" == "$runtime_database_url" ]] || {
  echo "DATABASE_URL and RUNTIME_DATABASE_URL must match." >&2
  exit 1
}

POSTGRES_SERVER_NAME="$server_name" \
POSTGRES_DATABASE="$database_name" \
POSTGRES_RUNTIME_USERNAME="$runtime_username" \
POSTGRES_HOSTED_PASSWORD="$hosted_password" \
RUNTIME_DATABASE_URL="$runtime_database_url" \
python3 - <<'PY'
import os
import sys
from hmac import compare_digest
from urllib.parse import parse_qs, unquote, urlsplit

parsed = urlsplit(os.environ["RUNTIME_DATABASE_URL"])
if parsed.scheme != "postgresql+psycopg":
    sys.exit("RUNTIME_DATABASE_URL must use postgresql+psycopg.")
if parsed.hostname != f'{os.environ["POSTGRES_SERVER_NAME"]}.postgres.database.azure.com':
    sys.exit("RUNTIME_DATABASE_URL host does not match PostgreSQL.")
if parsed.port != 5432:
    sys.exit("RUNTIME_DATABASE_URL must use port 5432.")
if unquote(parsed.username or "") != os.environ["POSTGRES_RUNTIME_USERNAME"]:
    sys.exit("RUNTIME_DATABASE_URL user does not match.")
if not compare_digest(unquote(parsed.password or ""), os.environ["POSTGRES_HOSTED_PASSWORD"]):
    sys.exit("RUNTIME_DATABASE_URL password does not match.")
if unquote(parsed.path.lstrip("/")) != os.environ["POSTGRES_DATABASE"]:
    sys.exit("RUNTIME_DATABASE_URL database does not match.")
if parse_qs(parsed.query).get("sslmode") != ["require"]:
    sys.exit("RUNTIME_DATABASE_URL must require TLS.")
PY

az account set --subscription "$subscription_id" >/dev/null
server_json="$(az postgres flexible-server show --subscription "$subscription_id" --resource-group "$resource_group" --name "$server_name" --query '{state:state,network:network.publicNetworkAccess,password:authConfig.passwordAuth,entra:authConfig.activeDirectoryAuth}' -o json)"
SERVER_JSON="$server_json" python3 - <<'PY'
import json
import os
import sys

server = json.loads(os.environ["SERVER_JSON"])
if server != {"state": "Ready", "network": "Enabled", "password": "Enabled", "entra": "Enabled"}:
    sys.exit("PostgreSQL server is not in the approved ready/dual-auth/public-network state.")
PY

for rule in allow-all-temporary allow-release-operator; do
  start="$(az postgres flexible-server firewall-rule show --subscription "$subscription_id" --resource-group "$resource_group" --server-name "$server_name" --name "$rule" --query startIpAddress -o tsv)"
  end="$(az postgres flexible-server firewall-rule show --subscription "$subscription_id" --resource-group "$resource_group" --server-name "$server_name" --name "$rule" --query endIpAddress -o tsv)"
  expected="0.0.0.0"
  [[ "$rule" == "allow-release-operator" ]] && expected="$operator_ip"
  [[ "$start" == "$expected" && "$end" == "$expected" ]] || {
    echo "PostgreSQL firewall rule $rule is not in the approved state." >&2
    exit 1
  }
done

az postgres flexible-server db show \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --server-name "$server_name" \
  --name "$database_name" \
  --output none >/dev/null

if ! PGPASSWORD="$hosted_password" PGSSLMODE=require \
  psql --host "${server_name}.postgres.database.azure.com" \
    --username "$runtime_username" \
    --dbname "$database_name" \
    --set ON_ERROR_STOP=on \
    --quiet \
    --command 'SELECT 1 FROM public.workflow_runs LIMIT 1;' >/dev/null 2>&1; then
  echo "PostgreSQL runtime credential could not read the canonical schema; output was withheld." >&2
  exit 1
fi

echo "PostgreSQL readiness passed: TLS runtime URL, least-privilege credential inputs, dual authentication, database, and scoped firewall rules are configured."
