#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
scratch_dir="$root_dir/backend/.tmp/runtime-secret-connection-test-$$"
bin_dir="$scratch_dir/bin"
az_log="$scratch_dir/az.log"
runtime_password='SecretPassword'
mkdir -p "$bin_dir"
trap 'rm -rf "$scratch_dir"' EXIT

cat >"$bin_dir/azd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "env" && "$2" == "get-value" ]]; then
  case "$3" in
    INFRASTRUCTURE_MODE) echo bootstrap ;;
    AZURE_SUBSCRIPTION_ID) echo 7df95e88-701c-4693-af77-3159f83b558d ;;
    AZURE_RESOURCE_GROUP) echo rg-langgraph-uw-foundry-public ;;
    AZURE_LOCATION) echo eastus2 ;;
    FOUNDRY_ACCOUNT_NAME) echo underwritingaccount ;;
    FOUNDRY_PROJECT_NAME) echo underwriting ;;
    POSTGRES_SERVER_NAME) echo underwritingpg ;;
    RUNTIME_DATABASE_URL|DATABASE_URL)
      echo "postgresql+psycopg://underwriting_runtime:${RUNTIME_PASSWORD:?}@underwritingpg.postgres.database.azure.com:5432/underwriting?sslmode=require"
      ;;
    FOUNDRY_RUNTIME_CONNECTION_NAME) echo underwritingruntimesecrets ;;
    HOSTED_AGENT_NAME) echo underwriting-hosted ;;
    APPLICATIONINSIGHTS_CONNECTION_STRING) echo placeholder ;;
    *) exit 0 ;;
  esac
  exit 0
fi
if [[ "$1" == "env" && "$2" == "set" ]]; then
  exit 0
fi
printf 'unexpected azd command: %s\n' "$*" >&2
exit 1
EOF
chmod 0755 "$bin_dir/azd"

cat >"$bin_dir/az" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"$AZ_LOG"
case "$1 $2" in
  "account set") exit 0 ;;
  "account show") echo 7df95e88-701c-4693-af77-3159f83b558d ;;
  "group show") echo eastus2 ;;
  "deployment group")
    parameters_source=""
    while [[ $# -gt 0 ]]; do
      if [[ "$1" == "--parameters" ]]; then
        parameters_source="$2"
        break
      fi
      shift
    done
    [[ "$parameters_source" == "@/dev/stdin" ]]
    payload="$(cat)"
    PAYLOAD="$payload" python3 - <<'PY'
import json
import os

payload = json.loads(os.environ["PAYLOAD"])
assert payload["parameters"]["runtimeConnectionName"]["value"] == "underwritingruntimesecrets"
assert "SecretPassword" in payload["parameters"]["runtimeDatabaseUrl"]["value"]
PY
    ;;
  "rest --method")
    printf '%s\n' '{"category":"CustomKeys","authType":"CustomKeys","target":"https://underwriting-runtime-secrets.local"}'
    ;;
  *)
    printf 'unexpected az command: %s\n' "$*" >&2
    exit 1
    ;;
esac
EOF
chmod 0755 "$bin_dir/az"

output="$(
  PATH="$bin_dir:$PATH" AZ_LOG="$az_log" RUNTIME_PASSWORD="$runtime_password" \
    bash "$root_dir/scripts/foundry/converge_runtime_secret_connection.sh"
)"
grep -Fq 'Converged Underwriting Foundry project CustomKeys runtime-secret connection.' \
  <<<"$output"
! grep -Fq "$runtime_password" <<<"$output"
! grep -Fq "$runtime_password" "$az_log"
grep -Fq -- '--parameters @/dev/stdin' "$az_log"
grep -Eq -- '--name underwriting-runtime-secret-[[:alnum:]._-]+' "$az_log"
! find "$scratch_dir" -type f ! -path "$bin_dir/*" -exec grep -Fq "$runtime_password" {} +
