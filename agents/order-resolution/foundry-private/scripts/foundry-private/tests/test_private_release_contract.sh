#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
scripts_dir="$root_dir/scripts/foundry-private"
scratch_dir="$scripts_dir/tests/.work-$$"
mkdir -p "$scratch_dir"
trap 'rm -rf -- "$scratch_dir"' EXIT

assert_no_match() {
  local pattern="$1"
  shift
  if grep -REn "$pattern" "$@"; then
    echo "Forbidden private release pattern matched: $pattern" >&2
    exit 1
  fi
}

profile="$scratch_dir/foundry-private.env"
cat >"$profile" <<'EOF'
CONTRACT_VERSION=2
DEPLOYMENT_LANE=foundry-private
AZURE_ENV_NAME=order-resolution-foundry-private
AZURE_SUBSCRIPTION_ID=7df95e88-701c-4693-af77-3159f83b558d
AZURE_RESOURCE_GROUP=rg-langgraph-ora-foundry-private
AZURE_LOCATION=eastus2
NAME_PREFIX=orderprivate
EOF

python3 "$scripts_dir/profile_gate.py" "$profile"
python3 "$scripts_dir/profile_gate.py" "$root_dir/deployment/profiles/foundry-private.env"
python3 "$scripts_dir/profile_gate.py" "$root_dir/deployment/profiles/foundry-private-bootstrap.env"
python3 "$scripts_dir/profile_gate.py" "$root_dir/deployment/profiles/foundry-private-package-validation.env"
python3 "$scripts_dir/profile_gate.py" --runtime "$root_dir/deployment/profiles/foundry-private-bootstrap.env"
sed 's/DEPLOYMENT_LANE=foundry-private/DEPLOYMENT_LANE=foundry-public/' "$profile" >"$scratch_dir/public.env"
if python3 "$scripts_dir/profile_gate.py" "$scratch_dir/public.env" >/dev/null 2>&1; then
  echo "Public deployment profiles must be rejected by private automation." >&2
  exit 1
fi
{
  sed -n '1,$p' "$profile"
  printf 'POSTGRES_OPERATOR_IP=203.0.113.10\n'
} >"$scratch_dir/public-network.env"
if python3 "$scripts_dir/profile_gate.py" "$scratch_dir/public-network.env" >/dev/null 2>&1; then
  echo "Private profiles must reject public-network bootstrap values." >&2
  exit 1
fi

printf 'Modify resource Microsoft.Example/widgets\n' |
  python3 "$scripts_dir/what_if_guard.py" >/dev/null
if printf 'Delete resource Microsoft.Example/widgets\n' |
  python3 "$scripts_dir/what_if_guard.py" >/dev/null 2>&1; then
  echo "Private what-if guard must reject delete changes." >&2
  exit 1
fi
if printf 'Replace resource Microsoft.Example/widgets\n' |
  python3 "$scripts_dir/what_if_guard.py" >/dev/null 2>&1; then
  echo "Private what-if guard must reject replace changes." >&2
  exit 1
fi
if printf '{"changeType":"Replace"}\n' |
  python3 "$scripts_dir/what_if_guard.py" >/dev/null 2>&1; then
  echo "Private what-if guard must reject JSON replace changes." >&2
  exit 1
fi

while IFS= read -r script; do
  bash -n "$script"
done < <(find "$scripts_dir" -maxdepth 1 -type f -name '*.sh' -print | sort)

grep -Fq 'AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd' "$scripts_dir/common.sh"
grep -Fq 'azd provision --cwd "$PRIVATE_AZD_DIR" --preview --no-prompt' "$scripts_dir/what_if.sh"
grep -Fq 'Delete or Replace' "$scripts_dir/what_if_guard.py"
grep -Fq 'Microsoft.Compute/virtualMachines' "$scripts_dir/iac_contract.sh"
grep -Fq 'openssl rand -hex 24' "$scripts_dir/bootstrap_env.sh"
grep -Fq "ssh-keygen -q -t ed25519" "$scripts_dir/bootstrap_env.sh"
grep -Fq 'capabilityHosts' "$scripts_dir/capability_host_cleanup.sh"
grep -Fq 'az vm run-command invoke' "$scripts_dir/runner_exec.sh"
grep -Fq -- '--command-id RunShellScript' "$scripts_dir/runner_exec.sh"
grep -Fq "'set -eu; cd %q;" "$scripts_dir/runner_exec.sh"
grep -Fq 'az rest' "$scripts_dir/runner_bootstrap.sh"
grep -Fq 'az vm run-command show' "$scripts_dir/runner_bootstrap.sh"
grep -Fq -- '--instance-view' "$scripts_dir/runner_bootstrap.sh"
grep -Fq 'protectedParameters' "$scripts_dir/runner_bootstrap.sh"
grep -Fq -- '--body "@$request_file"' "$scripts_dir/runner_bootstrap.sh"
grep -Fq 'az vm run-command delete' "$scripts_dir/runner_bootstrap.sh"
grep -Fq 'GIT_ASKPASS' "$scripts_dir/runner_bootstrap_remote.sh"
grep -Fq 'GIT_ASKPASS_REQUIRE=force' "$scripts_dir/runner_bootstrap_remote.sh"
grep -Fq 'export HOME=/root' "$scripts_dir/runner_bootstrap_remote.sh"
grep -Fq 'export HOME=/root' "$scripts_dir/runner_stage.sh"
grep -Fq '64 - ${#deployment_prefix}' "$scripts_dir/runner_postgres.sh"
grep -Fq 'type) == "number"' "$scripts_dir/model_preflight.sh"
grep -Fq 'azd auth login --managed-identity' "$scripts_dir/runner_bootstrap_remote.sh"
grep -Fq 'persistent_dir="/var/lib/order-resolution"' "$scripts_dir/runner_bootstrap_remote.sh"
grep -Fq 'persistent_env="$persistent_dir/private-runner.env"' "$scripts_dir/runner_bootstrap_remote.sh"
grep -Fq 'runner_bootstrap.sh' "$scripts_dir/provision.sh"
grep -Fq 'wait_foundry_ready.sh' "$scripts_dir/provision.sh"
grep -Fq 'DEPLOY_FOUNDRY_READY_RESOURCES false' "$scripts_dir/provision.sh"
grep -Fq 'DEPLOY_FOUNDRY_READY_RESOURCES true' "$scripts_dir/provision.sh"
grep -Fq 'publicNetworkAccess // .publicNetworkAccess // empty' "$scripts_dir/runner_acr_package.sh"
grep -Fq '"Disabled"' "$scripts_dir/runner_acr_package.sh"
assert_no_match 'az acr update .*public-network-enabled (true|Enabled)' "$scripts_dir/runner_acr_package.sh"
grep -Fq 'image="${registry_endpoint}/${repository}@${digest}"' "$scripts_dir/runner_acr_package.sh"
grep -Fq 'docker push "$tagged_image"' "$scripts_dir/runner_acr_package.sh"
if grep -Fq 'az acr build' "$scripts_dir/runner_acr_package.sh"; then
  echo "Private ACR packaging must build and push from the VNet runner." >&2
  exit 1
fi
grep -Fq 'copy_sanitized_tree' "$scripts_dir/runner_acr_package.sh"
grep -Fq -- "--exclude='.env*'" "$scripts_dir/runner_acr_package.sh"
grep -Fq 'quota:{current:$quota_current,limit:$quota_limit' "$scripts_dir/model_preflight.sh"
grep -Fq 'DB_SCHEMA_MANAGED_EXTERNALLY' "$scripts_dir/runner_deploy_runtime.sh"
grep -Fq 'PRIVATE_BACKEND_MANAGED_IDENTITY_NAME' "$scripts_dir/runner_deploy_runtime.sh"
grep -Fq 'backend_external_ingress:false' "$scripts_dir/verify.sh"
grep -Fq 'frontend_external_ingress:true' "$scripts_dir/verify.sh"
grep -Fq '.artifacts/private-packages' "$scripts_dir/sync_hosted_source.sh"
grep -Fq 'hosted_e2e' "$scripts_dir/release.sh"
grep -Fq 'runner_bootstrap' "$scripts_dir/release.sh"
grep -Fq 'browser_e2e' "$scripts_dir/release.sh"
grep -Fq 'evaluation' "$scripts_dir/release.sh"
grep -Fq 'telemetry' "$scripts_dir/release.sh"
grep -Fq 'runner_exec.sh" telemetry' "$scripts_dir/telemetry.sh"
grep -Fq 'az monitor app-insights query' "$scripts_dir/runner_telemetry.sh"
grep -Fq 'runner_telemetry.sh' "$scripts_dir/runner_stage.sh"
if grep -Fq 'provision.sh' "$scripts_dir/release.sh"; then
  echo "Routine private release must not provision infrastructure." >&2
  exit 1
fi
assert_no_match \
  'scripts/foundry/(hosted_e2e|run_foundry_eval|bootstrap_postgres_schema|provision_postgres_runtime_credentials)' \
  "$scripts_dir" --exclude-dir=tests --include='*.sh'
assert_no_match \
  '/tmp|read -[[:alnum:]]*[[:space:]]*-p|APPROVED|CONFIRM' \
  "$scripts_dir" --exclude-dir=tests --include='*.sh' --include='*.py'
assert_no_match '\./scripts/foundry/' "$root_dir/Makefile"

python3 - "$scripts_dir" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
for path in root.glob("*.sh"):
    source = path.read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        if "azd " not in stripped or stripped.startswith("#"):
            continue
        if (
            "private_azd" in stripped
            or "AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd" in stripped
            or "azd" in stripped and "common.sh" in str(path)
            or "private_require_command azd" in stripped
            or "command -v azd" in stripped
            or "for command in" in stripped
        ):
            continue
        raise SystemExit(f"azd call is not routed through the private user-agent wrapper: {path}: {line}")
PY

echo "Foundry-private script contract passed."
