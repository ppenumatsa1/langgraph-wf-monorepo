#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
project_dir="$(cd "$script_dir/.." && pwd -P)"
profile="$script_dir/profiles/azure-hosted.env"
bootstrap_profile="$script_dir/profiles/azure-hosted-bootstrap.env"
package_validation_profile="$script_dir/profiles/azure-hosted-package-validation.env"
scratch_dir="$project_dir/backend/.tmp/profile-contract-$$"
mkdir -p "$scratch_dir/bin"
trap 'rm -rf "$scratch_dir"' EXIT

for candidate in "$profile" "$bootstrap_profile" "$package_validation_profile"; do
  bash "$script_dir/profile.sh" validate "$candidate"
  for forbidden_key in \
    RUNTIME_DATABASE_URL DATABASE_URL APPLICATIONINSIGHTS_CONNECTION_STRING \
    POSTGRES_ADMIN_PASSWORD POSTGRES_SERVER_ADMIN_PASSWORD \
    POSTGRES_HOSTED_PASSWORD POSTGRES_SERVER_NAME \
    FOUNDRY_ACCOUNT_NAME AZURE_CONTAINER_REGISTRY_NAME; do
    ! grep -q "^${forbidden_key}=" "$candidate"
  done
done

cat >"$scratch_dir/bin/azd" <<'EOF'
#!/usr/bin/env bash
printf '%s|%s\n' "$PWD" "$*" >> "$AZD_LOG"
EOF
chmod +x "$scratch_dir/bin/azd"

AZD_COMMAND="$scratch_dir/bin/azd" AZD_LOG="$scratch_dir/azd.log" \
  bash "$script_dir/apply-azd-profile.sh" "$profile"

grep -Fq 'azure-hosted|env set AZURE_SUBSCRIPTION_ID 7df95e88-701c-4693-af77-3159f83b558d' "$scratch_dir/azd.log"
grep -Fq 'env set AZURE_RESOURCE_GROUP rg-langgraph-ora-azure-hosted' "$scratch_dir/azd.log"
grep -Fq 'env set AZURE_LOCATION eastus2' "$scratch_dir/azd.log"
grep -Fq 'env set NAME_PREFIX orderresolution' "$scratch_dir/azd.log"

base_ref="HEAD"
if ! git -C "$project_dir" rev-parse --verify HEAD >/dev/null 2>&1; then
  base_ref="$(git -C "$project_dir" hash-object -t tree /dev/null)"
fi
router_output="$("$project_dir/scripts/skills/deployment-mode-router.sh" "$base_ref")"
grep -Fxq 'deploy_mode=app_only' <<<"$router_output"
