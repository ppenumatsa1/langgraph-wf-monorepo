#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
script_path="$root_dir/scripts/foundry/prepare_package_validation_env.sh"
profile_path="$root_dir/deployment/profiles/foundry-public-package-validation.env"
scratch_dir="$root_dir/backend/.tmp/package-validation-contract-$$"
mkdir -p "$scratch_dir/bin"
trap 'rm -rf "$scratch_dir"' EXIT

bash -n "$script_path"
bash "$root_dir/deployment/profile.sh" validate "$profile_path"

cat >"$scratch_dir/bin/azd" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s|%s\n' "$PWD" "$*" >>"$AZD_LOG"
if [[ "$1" == "env" && "$2" == "set" ]]; then
  cwd=''
  for ((i = 1; i <= $#; i++)); do
    if [[ "${!i}" == "--cwd" ]]; then
      next=$((i + 1))
      cwd="${!next}"
      break
    fi
  done
  if [[ -n "$cwd" ]]; then
    mkdir -p "$cwd/.azure"
    printf '%s\n' '{"version":1,"defaultEnvironment":"underwriting-foundry-public"}' >"$cwd/.azure/config.json"
  fi
fi
EOF
chmod +x "$scratch_dir/bin/azd"

cat >"$scratch_dir/bin/az" <<'EOF'
#!/usr/bin/env bash
echo "prepare_package_validation_env.sh must not call az" >&2
exit 1
EOF
chmod +x "$scratch_dir/bin/az"

cat >"$scratch_dir/bin/curl" <<'EOF'
#!/usr/bin/env bash
echo "prepare_package_validation_env.sh must not call curl" >&2
exit 1
EOF
chmod +x "$scratch_dir/bin/curl"

PATH="$scratch_dir/bin:$PATH" AZD_LOG="$scratch_dir/azd.log" bash "$script_path" >/dev/null

grep -Fq 'env set -e underwriting-package-validation AZURE_ENV_NAME underwriting-package-validation --cwd ' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation AZURE_SUBSCRIPTION_ID 7df95e88-701c-4693-af77-3159f83b558d' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation AZURE_RESOURCE_GROUP rg-langgraph-uw-foundry-public' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation AZURE_LOCATION eastus2' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation NAME_PREFIX underwriting' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation INFRASTRUCTURE_MODE reuse' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation FOUNDRY_LOCAL_VALIDATION_MODE package_validation' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation RESOURCE_NAME_SUFFIX 543d527c' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation FOUNDRY_ACCOUNT_NAME underwriting543d527cai' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation CONTAINER_REGISTRY_NAME underwriting543d527cacr' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation BACKEND_CONTAINER_APP_NAME underwriting543d527c-backend' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation FRONTEND_CONTAINER_APP_NAME underwriting543d527c-frontend' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation FOUNDRY_MODEL_SKU_NAME DataZoneStandard' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation FOUNDRY_MODEL_CAPACITY 1500' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation FOUNDRY_EVAL_MODEL underwriting-gpt-4-1-mini-evaluation' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation APPLICATIONINSIGHTS_CONNECTION_STRING InstrumentationKey=00000000-0000-0000-0000-000000000000' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation API_BASE_URL https://underwriting543d527c-backend.package-validation.invalid' "$scratch_dir/azd.log"
grep -Fq 'env set -e underwriting-package-validation WEB_URL https://underwriting543d527c-frontend.package-validation.invalid' "$scratch_dir/azd.log"

bash "$root_dir/scripts/foundry/sync_hosted_source.sh" >/dev/null
grep -Fq 'PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple' \
  "$root_dir/infra/foundry-hosted/agent/Dockerfile"
test -f "$root_dir/infra/foundry-hosted/agent/backend/foundry/main.py"
