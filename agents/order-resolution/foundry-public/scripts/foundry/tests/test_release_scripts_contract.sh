#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
scratch_dir="$root_dir/backend/.tmp/release-script-contract-$$"
mkdir -p "$scratch_dir"
trap 'rm -rf "$scratch_dir"' EXIT

for script in \
  "$root_dir/scripts/foundry/preflight_models.sh" \
  "$root_dir/scripts/foundry/converge_runtime_secret_connection.sh" \
  "$root_dir/scripts/foundry/ensure_hosted_agent_rbac.sh" \
  "$root_dir/scripts/foundry/hosted_smoke.sh" \
  "$root_dir/scripts/foundry/verify_deployment.sh" \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh" \
  "$root_dir/scripts/foundry/deploy_public_backend.sh" \
  "$root_dir/scripts/foundry/deploy_public_frontend.sh" \
  "$root_dir/scripts/foundry/deploy_public_dev.sh"; do
  bash -n "$script"
done

grep -Fq '7df95e88-701c-4693-af77-3159f83b558d' \
  "$root_dir/deployment/profiles/foundry-public.env"
grep -Fq 'AZURE_RESOURCE_GROUP=rg-langgraph-ora-foundry-public' \
  "$root_dir/deployment/profiles/foundry-public.env"
grep -Fq 'AZURE_LOCATION=eastus2' "$root_dir/deployment/profiles/foundry-public.env"
grep -Fq 'shared_profile="$ROOT_DIR/../deployment/profiles/foundry-public.env"' \
  "$root_dir/scripts/foundry/deploy_public_dev.sh"
grep -Fq 'legacy_pending_cutover' "$root_dir/scripts/foundry/deploy_public_dev.sh"
grep -Fq 'FOUNDRY_PACKAGE_ENV_NAME ?= order-resolution-package-validation' \
  "$root_dir/Makefile"
grep -Fq 'FOUNDRY_PACKAGE_VALIDATION_PROFILE ?= deployment/profiles/foundry-public-package-validation.env' \
  "$root_dir/Makefile"
grep -Fq 'foundry-package-validation-env' "$root_dir/Makefile"
grep -Fq 'prepare_package_validation_env.sh' "$root_dir/Makefile"
grep -Fq 'azd package --all --environment "$(FOUNDRY_PACKAGE_ENV_NAME)" --no-prompt' \
  "$root_dir/Makefile"
grep -Fq 'Local-only packaging selector' \
  "$root_dir/deployment/profiles/foundry-public-package-validation.env"
grep -Fq '.artifacts/releases/$FOUNDRY_RELEASE_ID' \
  "$root_dir/scripts/foundry/deploy_public_dev.sh"
grep -Fq 'release_evidence.py finalize' "$root_dir/Makefile"

grep -Fq 'Cognitive Services OpenAI User' \
  "$root_dir/scripts/foundry/ensure_hosted_agent_rbac.sh"
grep -Fq -- '--assignee-object-id' \
  "$root_dir/scripts/foundry/ensure_hosted_agent_rbac.sh"
grep -Fq 'az cognitiveservices usage list' \
  "$root_dir/scripts/foundry/preflight_models.sh"
! grep -Eq 'deployment (create|update|delete)' \
  "$root_dir/scripts/foundry/preflight_models.sh"
grep -Fq 'FOUNDRY_RUNTIME_CONNECTION_NAME' \
  "$root_dir/scripts/foundry/converge_runtime_secret_connection.sh"
! grep -Eq '/tmp|mktemp' \
  "$root_dir/scripts/foundry/converge_runtime_secret_connection.sh" \
  "$root_dir/scripts/foundry/verify_deployment.sh"
grep -Fq 'rm -f -- "$PARAMETER_FILE"' \
  "$root_dir/scripts/foundry/converge_runtime_secret_connection.sh"
grep -Fq -- '--subscription "$subscription_id"' \
  "$root_dir/scripts/foundry/converge_runtime_secret_connection.sh"
grep -Fq 'credentials.database_url' \
  "$root_dir/scripts/foundry/deploy_hosted_container.py"
grep -Fq 'FOUNDRY_HOSTED_OTEL_SERVICE_NAME' \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh"
grep -Fq 'FOUNDRY_OTEL_SERVICE_NAMESPACE' \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh"
! grep -Fq 'require("RUNTIME_DATABASE_URL")' \
  "$root_dir/scripts/foundry/deploy_hosted_container.py"
! grep -Fq 'require("RUNTIME_DATABASE_URL")' \
  "$root_dir/scripts/foundry/verify_hosted_agent.py"
grep -Fq -- '--subscription "$subscription_id"' \
  "$root_dir/scripts/foundry/ensure_hosted_agent_rbac.sh"
grep -Fq -- '--subscription "$SUBSCRIPTION_ID"' \
  "$root_dir/scripts/foundry/verify_telemetry.sh"
grep -Fq '    - task_completion' "$root_dir/backend/eval.yaml"
grep -Fq '    - coherence' "$root_dir/backend/eval.yaml"

for script in \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh" \
  "$root_dir/scripts/foundry/deploy_public_backend.sh" \
  "$root_dir/scripts/foundry/deploy_public_frontend.sh"; do
  grep -Fq '@${image_digest}' "$script"
  grep -Fq 'source_revision=uncommitted' "$script"
done
grep -Fq 'launch_hosted_agent.py' "$root_dir/scripts/foundry/sync_hosted_source.sh"
grep -Fq 'package-validation.invalid' \
  "$root_dir/scripts/foundry/prepare_package_validation_env.sh"
grep -Fq 'Dockerfile.backend-release' "$root_dir/scripts/foundry/deploy_public_backend.sh"

python3 - \
  "$root_dir/scripts/foundry/deploy_public_backend.sh" \
  "$root_dir/scripts/foundry/deploy_public_frontend.sh" <<'PY'
import re
import sys
from pathlib import Path

for raw_path in sys.argv[1:]:
    path = Path(raw_path)
    source = path.read_text(encoding="utf-8")
    assert 'subscription_id="$(required_env AZURE_SUBSCRIPTION_ID)"' in source, path
    assert 'az account set --subscription "$subscription_id"' in source, path
    assert "7df95e88-701c-4693-af77-3159f83b558d" in source, path
    assert "rg-langgraph-ora-foundry-public" in source, path

    normalized = re.sub(r"\\\n[ \t]*", " ", source)
    commands = re.findall(r"(?m)^[ \t]*az [^\n]+", normalized)
    assert commands, path
    for command in commands:
        if command.startswith("az account set "):
            continue
        assert '--subscription "$subscription_id"' in command, (path, command)
PY

grep -Fq 'subscription_id="$(require_env AZURE_SUBSCRIPTION_ID' \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh"
grep -Fq 'az account set --subscription "$subscription_id"' \
  "$root_dir/scripts/foundry/deploy_hosted_container.sh"
grep -Fq 'AZURE_SUBSCRIPTION_ID="$(required_env AZURE_SUBSCRIPTION_ID)"' \
  "$root_dir/scripts/foundry/deploy_public_dev.sh"
grep -Fq 'az account set --subscription "$AZURE_SUBSCRIPTION_ID"' \
  "$root_dir/scripts/foundry/deploy_public_dev.sh"

az bicep build \
  --file "$root_dir/infra/foundry-hosted/iac/modules/foundry-project-runtime-secret-connection.bicep" \
  --stdout | python3 -c '
import json
import sys

template = json.load(sys.stdin)
assert template["parameters"]["runtimeDatabaseUrl"]["type"] == "securestring"
resources = template["resources"]
connections = [
    item for item in resources
    if item["type"] == "Microsoft.CognitiveServices/accounts/projects/connections"
]
assert len(connections) == 1
properties = connections[0]["properties"]
assert properties["category"] == "CustomKeys"
assert properties["authType"] == "CustomKeys"
assert "database_url" in properties["credentials"]["keys"]
'

if FOUNDRY_DEPLOY_MODE=full \
  bash "$root_dir/scripts/foundry/deploy_public_dev.sh" \
  >"$scratch_dir/deploy-mode-contract.out" 2>&1; then
  echo "FOUNDRY_DEPLOY_MODE override must be rejected." >&2
  exit 1
fi
grep -Fq 'FOUNDRY_DEPLOY_MODE is no longer supported' \
  "$scratch_dir/deploy-mode-contract.out"
