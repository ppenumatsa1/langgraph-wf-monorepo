#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
prepare_script="$root_dir/scripts/foundry/prepare_bootstrap_env.sh"
template="$root_dir/infra/foundry-hosted/iac/main.bicep"
mock_bin="$root_dir/scripts/foundry/tests/mock-bin"
hydration_mock_bin="$root_dir/scripts/foundry/tests/mock-hydration-bin"
scratch_dir="$root_dir/backend/.tmp/bootstrap-contract-$$"
mkdir -p "$scratch_dir"
trap 'rm -rf "$scratch_dir"' EXIT

output="$(PATH="$mock_bin:$PATH" bash "$prepare_script" 2>&1)"
for expected in \
  'set INFRASTRUCTURE_MODE=bootstrap' \
  'set NAME_PREFIX=underwriting' \
  'set RESOURCE_NAME_SUFFIX=eb7a06fe' \
  'set POSTGRES_SERVER_NAME=underwritingeb7a06fepg' \
  'set CONTAINER_REGISTRY_NAME=underwritingeb7a06feacr' \
  'set BACKEND_IMAGE_REPOSITORY=underwriting-public-backend' \
  'set FRONTEND_IMAGE_REPOSITORY=underwriting-public-frontend' \
  'set FOUNDRY_MODEL_SKU_NAME=DataZoneStandard' \
  'set FOUNDRY_MODEL_CAPACITY=1500' \
  'set FOUNDRY_EVAL_MODEL=underwriting-gpt-4-1-mini-evaluation' \
  'set HOSTED_AGENT_NAME=underwriting-hosted' \
  'set FOUNDRY_RUNTIME_CONNECTION_NAME=underwritingruntimesecrets'; do
  grep -Fxq "$expected" <<<"$output"
done

grep -Fq "param infrastructureMode string = 'bootstrap'" "$template"
grep -Fq "resource foundryAccountBootstrap" "$template"
grep -Fq "resource foundryProjectBootstrap" "$template"
grep -Fq "resource foundryChatDeploymentBootstrap" "$template"
grep -Fq "resource foundryEmbeddingsDeploymentBootstrap" "$template"
grep -Fq "resource foundryEvaluationDeploymentBootstrap" "$template"
grep -B5 -A2 "param foundryChatModelSkuName string = 'DataZoneStandard'" "$template" | grep -Fq "'DataZoneStandard'"
grep -Fq "resource postgresServerBootstrap" "$template"
grep -Fq "resource evaluationStorageAccountBootstrap" "$template"
grep -A20 "resource evaluationStorageAccountBootstrap" "$template" | grep -Fq "publicNetworkAccess: 'Enabled'"
grep -A20 "resource evaluationStorageAccountBootstrap" "$template" | grep -Fq "bypass: 'AzureServices'"
grep -A20 "resource evaluationStorageAccountBootstrap" "$template" | grep -Fq "defaultAction: 'Deny'"
grep -A50 "resource backendContainerAppBootstrap" "$template" | grep -Fq "external: false"
grep -A50 "resource frontendContainerAppBootstrap" "$template" | grep -Fq "external: true"
grep -Fq "name: 'NGINX_API_UPSTREAM'" "$template"
grep -Fq "name: 'DB_SCHEMA_MANAGED_EXTERNALLY'" "$template"
grep -Fq "output FOUNDRY_RUNTIME_CONNECTION_NAME" "$template"
grep -Fq "output FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME" "$template"
grep -Fq "output FOUNDRY_EVAL_MODEL" "$template"
grep -Fq "reference(foundryAccountId, '2025-06-01').endpoint" "$template"
! grep -Fq "reference(foundryAccountId, '2025-06-01').properties.endpoint" "$template"
grep -Fq 'set_value INFRASTRUCTURE_MODE reuse' "$root_dir/scripts/foundry/bootstrap_azd_env.sh"
grep -Fq 'set_value NAME_PREFIX "$normalized_prefix"' "$root_dir/scripts/foundry/bootstrap_azd_env.sh"
grep -Fq 'AZURE_RESOURCE_GROUP=rg-langgraph-uw-foundry-public' "$root_dir/deployment/profiles/foundry-public.env"
grep -Fq 'AZURE_RESOURCE_GROUP=rg-langgraph-uw-foundry-public' "$root_dir/deployment/profiles/foundry-public-bootstrap.env"

az bicep build --file "$template" --stdout | python3 -c '
import json
import sys

template = json.load(sys.stdin)
assignments = [
    resource for resource in template["resources"]
    if resource["type"] == "Microsoft.Authorization/roleAssignments"
]
assert len(assignments) == 10
assert all("scope" in assignment for assignment in assignments)
assert all(resource.get("condition") for resource in assignments)
'

MOCK_AZD_LOG="$scratch_dir/hydrated.env" \
  PATH="$hydration_mock_bin:$PATH" \
  bash "$root_dir/scripts/foundry/bootstrap_azd_env.sh" >/dev/null

for output_name in \
  AZURE_AI_PROJECT_ENDPOINT AZURE_AI_PROJECT_ID FOUNDRY_PROJECT_ENDPOINT \
  FOUNDRY_PROJECTS_ENDPOINT FOUNDRY_ACCOUNT_NAME FOUNDRY_PROJECT_NAME \
  FOUNDRY_HOSTED_RESPONSES_URL FOUNDRY_RESPONSES_ENDPOINT FOUNDRY_MODEL_DEPLOYMENT_NAME \
  FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME FOUNDRY_EVAL_MODEL HOSTED_AGENT_NAME \
  FOUNDRY_RUNTIME_CONNECTION_NAME AZURE_OPENAI_ENDPOINT AZURE_CONTAINER_REGISTRY_NAME \
  AZURE_CONTAINER_REGISTRY_ENDPOINT APPLICATIONINSIGHTS_RESOURCE_ID \
  APPLICATIONINSIGHTS_CONNECTION_STRING LOG_ANALYTICS_WORKSPACE_ID \
  AZURE_POSTGRES_SERVER_FQDN POSTGRES_SERVER_NAME POSTGRES_SERVER_LOCATION \
  POSTGRES_DATABASE AZURE_CONTAINER_APPS_ENVIRONMENT_ID \
  CONTAINER_APPS_ENVIRONMENT_NAME BACKEND_CONTAINER_APP_ID \
  BACKEND_CONTAINER_APP_NAME FRONTEND_CONTAINER_APP_ID \
  FRONTEND_CONTAINER_APP_NAME PUBLIC_BACKEND_MANAGED_IDENTITY_NAME \
  PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME BACKEND_IMAGE_REPOSITORY \
  FRONTEND_IMAGE_REPOSITORY API_BASE_URL WEB_URL; do
  grep -q "^${output_name}=" "$scratch_dir/hydrated.env"
done
