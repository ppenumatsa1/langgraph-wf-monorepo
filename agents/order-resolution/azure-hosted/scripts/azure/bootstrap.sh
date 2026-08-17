#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

"$SCRIPT_DIR/preflight.sh"
for key in POSTGRES_ADMIN_OBJECT_ID POSTGRES_ADMIN_PRINCIPAL_NAME; do
  [[ -n "$(azd_value "$key")" ]] || {
    echo "$key is required for administrator-owned PostgreSQL DDL." >&2
    exit 1
  }
done

if [[ -z "$(azd_value POSTGRES_SERVER_ADMIN_LOGIN)" ]]; then
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env set POSTGRES_SERVER_ADMIN_LOGIN pgbootstrapadmin \
      --cwd "$ROOT_DIR" --no-prompt >/dev/null
fi

if [[ -z "$(azd_value POSTGRES_SERVER_ADMIN_PASSWORD)" ]]; then
  postgres_server_admin_password="$(
    python3 - <<'PY'
import secrets
import string

required = [
    secrets.choice(string.ascii_uppercase),
    secrets.choice(string.ascii_lowercase),
    secrets.choice(string.digits),
    secrets.choice("!#%+-_=:@"),
]
required.extend(secrets.choice(string.ascii_letters + string.digits + "!#%+-_=:@") for _ in range(28))
secrets.SystemRandom().shuffle(required)
print("".join(required))
PY
  )"
  AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
    azd env set POSTGRES_SERVER_ADMIN_PASSWORD "$postgres_server_admin_password" \
      --cwd "$ROOT_DIR" --no-prompt >/dev/null
  unset postgres_server_admin_password
fi

"$SCRIPT_DIR/provision_infrastructure.sh"

subscription_id="$(required_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_azd_value AZURE_RESOURCE_GROUP)"
server_name="$(required_azd_value POSTGRES_SERVER_NAME)"
admin_object_id="$(required_azd_value POSTGRES_ADMIN_OBJECT_ID)"
admin_principal_name="$(required_azd_value POSTGRES_ADMIN_PRINCIPAL_NAME)"
admin_principal_type="$(required_azd_value POSTGRES_ADMIN_PRINCIPAL_TYPE)"

for _attempt in $(seq 1 40); do
  server_state="$(
    az postgres flexible-server show \
      --subscription "$subscription_id" \
      --resource-group "$resource_group" \
      --name "$server_name" \
      --query state \
      --output tsv
  )"
  [[ "$server_state" == "Ready" ]] && break
  sleep 15
done
[[ "${server_state:-}" == "Ready" ]] || {
  echo "AUTOMATION BLOCKED: PostgreSQL did not become Ready." >&2
  exit 1
}

admins="$(
  az postgres flexible-server microsoft-entra-admin list \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --server-name "$server_name" \
    --output json
)"
existing_admin_count="$(jq 'length' <<<"$admins")"
if [[ "$existing_admin_count" == "0" ]]; then
  az postgres flexible-server microsoft-entra-admin create \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --server-name "$server_name" \
    --display-name "$admin_principal_name" \
    --object-id "$admin_object_id" \
    --type "$admin_principal_type" \
    --output none
else
  jq -e \
    --arg object_id "$admin_object_id" \
    --arg principal_name "$admin_principal_name" \
    --arg principal_type "$admin_principal_type" \
    'length == 1
     and .[0].objectId == $object_id
     and .[0].principalName == $principal_name
     and .[0].principalType == $principal_type' \
    <<<"$admins" >/dev/null || {
      echo "AUTOMATION BLOCKED: PostgreSQL has an unexpected Entra administrator." >&2
      exit 1
    }
fi
