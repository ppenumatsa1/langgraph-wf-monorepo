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
    printf '%s\n' '{"version":1,"defaultEnvironment":"order-resolution-package-validation"}' >"$cwd/.azure/config.json"
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

grep -Fq 'env set -e order-resolution-package-validation AZURE_ENV_NAME order-resolution-package-validation --cwd ' "$scratch_dir/azd.log"
grep -Fq 'env set -e order-resolution-package-validation AZURE_SUBSCRIPTION_ID 7df95e88-701c-4693-af77-3159f83b558d' "$scratch_dir/azd.log"
grep -Fq 'env set -e order-resolution-package-validation AZURE_RESOURCE_GROUP rg-langgraph-ora-foundry-public' "$scratch_dir/azd.log"
grep -Fq 'env set -e order-resolution-package-validation AZURE_LOCATION eastus2' "$scratch_dir/azd.log"
grep -Fq 'env set -e order-resolution-package-validation NAME_PREFIX orderresolution' "$scratch_dir/azd.log"
grep -Fq 'env set -e order-resolution-package-validation INFRASTRUCTURE_MODE reuse' "$scratch_dir/azd.log"
grep -Fq 'env set -e order-resolution-package-validation FOUNDRY_LOCAL_VALIDATION_MODE package_validation' "$scratch_dir/azd.log"
grep -Fq 'env set -e order-resolution-package-validation RESOURCE_NAME_SUFFIX a273f84f' "$scratch_dir/azd.log"
grep -Fq 'env set -e order-resolution-package-validation FOUNDRY_ACCOUNT_NAME orderresoluta273f84fai' "$scratch_dir/azd.log"
grep -Fq 'env set -e order-resolution-package-validation CONTAINER_REGISTRY_NAME orderresoluta273f84facr' "$scratch_dir/azd.log"
grep -Fq 'env set -e order-resolution-package-validation BACKEND_CONTAINER_APP_NAME orderresoluta273f84f-backend' "$scratch_dir/azd.log"
grep -Fq 'env set -e order-resolution-package-validation FRONTEND_CONTAINER_APP_NAME orderresoluta273f84f-frontend' "$scratch_dir/azd.log"
grep -Fq 'env set -e order-resolution-package-validation OTEL_EXPORTER_OTLP_TRACES_ENDPOINT https://package-validation.invalid/v1/traces' "$scratch_dir/azd.log"
grep -Fq 'env set -e order-resolution-package-validation APPLICATIONINSIGHTS_CONNECTION_STRING InstrumentationKey=00000000-0000-0000-0000-000000000000' "$scratch_dir/azd.log"
grep -Fq 'env set -e order-resolution-package-validation API_BASE_URL https://orderresoluta273f84f-backend.package-validation.invalid' "$scratch_dir/azd.log"
grep -Fq 'env set -e order-resolution-package-validation WEB_URL https://orderresoluta273f84f-frontend.package-validation.invalid' "$scratch_dir/azd.log"
grep -Fqx '{"version":1,"defaultEnvironment":"order-resolution-foundry-public"}' \
  "$root_dir/infra/foundry-hosted/.azure/config.json"

bash "$root_dir/scripts/foundry/sync_hosted_source.sh" >/dev/null
grep -Fq 'PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple' \
  "$root_dir/backend/Dockerfile.hosted"
grep -Fq 'CMD ["python", ".deployment/launch_hosted_agent.py"]' \
  "$root_dir/infra/foundry-hosted/agent/Dockerfile"
test -f "$root_dir/infra/foundry-hosted/agent/.deployment/launch_hosted_agent.py"
