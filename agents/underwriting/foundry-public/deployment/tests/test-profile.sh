#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
project_dir="$(cd "$script_dir/.." && pwd -P)"
profile="$script_dir/profiles/foundry-public.env"
bootstrap_profile="$script_dir/profiles/foundry-public-bootstrap.env"
package_validation_profile="$script_dir/profiles/foundry-public-package-validation.env"
scratch_dir="$project_dir/backend/.tmp/profile-contract-$$"
mkdir -p "$scratch_dir/bin"
trap 'rm -rf "$scratch_dir"' EXIT

for candidate in "$profile" "$bootstrap_profile" "$package_validation_profile"; do
  bash "$script_dir/profile.sh" validate "$candidate"
  for forbidden_key in \
    RUNTIME_DATABASE_URL DATABASE_URL APPLICATIONINSIGHTS_CONNECTION_STRING \
    POSTGRES_ADMIN_PASSWORD POSTGRES_HOSTED_PASSWORD POSTGRES_SERVER_NAME \
    FOUNDRY_ACCOUNT_NAME AZURE_CONTAINER_REGISTRY_NAME; do
    ! grep -q "^${forbidden_key}=" "$candidate"
  done
done

grep -Fxq 'AZURE_SUBSCRIPTION_ID=7df95e88-701c-4693-af77-3159f83b558d' "$profile"
grep -Fxq 'AZURE_RESOURCE_GROUP=rg-langgraph-uw-foundry-public' "$profile"
grep -Fxq 'AZURE_LOCATION=eastus2' "$profile"
grep -Fxq 'AZURE_ENV_NAME=underwriting-bootstrap' "$bootstrap_profile"
grep -Fxq 'AZURE_ENV_NAME=underwriting-package-validation' "$package_validation_profile"
! grep -Eq '00000000-0000-0000-0000-000000000000|203\.0\.113\.10|package-validation\.invalid' \
  "$profile" "$bootstrap_profile" "$package_validation_profile"

cat >"$scratch_dir/bin/azd" <<'EOF'
#!/usr/bin/env bash
printf '%s|%s\n' "$PWD" "$*" >> "$AZD_LOG"
EOF
chmod +x "$scratch_dir/bin/azd"

AZD_COMMAND="$scratch_dir/bin/azd" AZD_LOG="$scratch_dir/azd.log" \
  bash "$script_dir/apply-azd-profile.sh" "$profile"

grep -Fq 'foundry-public/infra/foundry-hosted|env set AZURE_SUBSCRIPTION_ID 7df95e88-701c-4693-af77-3159f83b558d' "$scratch_dir/azd.log"
grep -Fq 'env set AZURE_RESOURCE_GROUP rg-langgraph-uw-foundry-public' "$scratch_dir/azd.log"
grep -Fq 'env set AZURE_LOCATION eastus2' "$scratch_dir/azd.log"
grep -Fq 'env set NAME_PREFIX underwriting' "$scratch_dir/azd.log"
! grep -Fq 'agents/order-resolution' "$script_dir/apply-azd-profile.sh"

router_output="$("$project_dir/scripts/skills/deployment-mode-router.sh" HEAD)"
grep -Fxq 'deploy_mode=app_only' <<<"$router_output"

unborn_repo="$scratch_dir/unborn"
mkdir -p "$unborn_repo/scripts/skills"
cp "$project_dir/scripts/skills/deployment-mode-router.sh" "$unborn_repo/scripts/skills/"
(
  cd "$unborn_repo"
  git init --quiet
  printf 'lane contract\n' > release-note.txt
  output="$(bash scripts/skills/deployment-mode-router.sh HEAD)"
  grep -Fxq 'deploy_mode=app_only' <<<"$output"
)
