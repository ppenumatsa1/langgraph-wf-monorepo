#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

[[ "${AZURE_BOOTSTRAP_APPROVED:-}" == "true" ]] || {
  echo "Set AZURE_BOOTSTRAP_APPROVED=true only after reviewing the subscription-scope Bicep preview." >&2
  exit 2
}

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

AZURE_DEV_USER_AGENT=microsoft_foundry_skill \
  azd provision --cwd "$ROOT_DIR" --no-prompt
