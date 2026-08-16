#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd -P)"
prepare_script="$root_dir/scripts/foundry/prepare_bootstrap_env.sh"
template="$root_dir/infra/foundry-hosted/iac/main.bicep"
compose_file="$root_dir/docker-compose.yml"
free_port_script="$root_dir/scripts/local/find_free_port.py"
postgres_bootstrap_script="$root_dir/scripts/foundry/bootstrap_postgres_schema.sh"
test_postgres_runner="$root_dir/scripts/local/run_with_test_postgres.sh"
mock_bin="$root_dir/scripts/foundry/tests/mock-bin"
hydration_mock_bin="$root_dir/scripts/foundry/tests/mock-hydration-bin"
scratch_dir="$root_dir/backend/.tmp/bootstrap-contract-$$"
mkdir -p "$scratch_dir"
trap 'rm -rf "$scratch_dir"' EXIT

output="$(PATH="$mock_bin:$PATH" bash "$prepare_script" 2>&1)"
for expected in \
  'set INFRASTRUCTURE_MODE=bootstrap' \
  'set NAME_PREFIX=orderresolution' \
  'set RESOURCE_NAME_SUFFIX=a273f84f' \
  'set POSTGRES_SERVER_NAME=orderresoluta273f84fpg' \
  'set CONTAINER_REGISTRY_NAME=orderresoluta273f84facr' \
  'set BACKEND_IMAGE_REPOSITORY=order-resolution-public-backend' \
  'set FRONTEND_IMAGE_REPOSITORY=order-resolution-public-frontend' \
  'set FOUNDRY_MODEL_SKU_NAME=Standard' \
  'set HOSTED_AGENT_NAME=order-resolution-hosted' \
  'set FOUNDRY_RUNTIME_CONNECTION_NAME=orderresolutionruntimesecrets'; do
  grep -Fxq "$expected" <<<"$output"
done

grep -Fq "param infrastructureMode string = 'bootstrap'" "$template"
grep -Fq "resource foundryAccountBootstrap" "$template"
grep -Fq "resource foundryProjectBootstrap" "$template"
grep -Fq "resource foundryChatDeploymentBootstrap" "$template"
grep -Fq "resource foundryEmbeddingsDeploymentBootstrap" "$template"
grep -Fq "resource foundryEvaluationDeploymentBootstrap" "$template"
grep -B5 -A2 "param foundryChatModelSkuName string = 'Standard'" "$template" | grep -Fq "'DataZoneStandard'"
grep -Fq "resource postgresServerBootstrap" "$template"
grep -Fq "resource evaluationStorageAccountBootstrap" "$template"
grep -A20 "resource evaluationStorageAccountBootstrap" "$template" | grep -Fq "publicNetworkAccess: 'Enabled'"
grep -A20 "resource evaluationStorageAccountBootstrap" "$template" | grep -Fq "bypass: 'AzureServices'"
grep -A20 "resource evaluationStorageAccountBootstrap" "$template" | grep -Fq "defaultAction: 'Deny'"
grep -A50 "resource backendContainerAppBootstrap" "$template" | grep -Fq "external: false"
grep -A50 "resource frontendContainerAppBootstrap" "$template" | grep -Fq "external: true"
grep -Fq "set_env INFRASTRUCTURE_MODE reuse" "$root_dir/scripts/foundry/bootstrap_azd_env.sh"
grep -Fq "postgres-bootstrap:" "$compose_file"
grep -A12 "postgres-bootstrap:" "$compose_file" | grep -Fq "python -m app.sql.bootstrap"
grep -A12 "postgres-bootstrap:" "$compose_file" | grep -Fq "condition: service_healthy"
grep -A16 "^  backend:" "$compose_file" | grep -Fq "condition: service_completed_successfully"
free_port="$(python3 "$free_port_script")"
[[ "$free_port" =~ ^[0-9]+$ ]]
(( free_port >= 20000 && free_port < 30000 ))
grep -Fq "PostgresCheckpointerFactory" "$postgres_bootstrap_script"
grep -Fq "LANGGRAPH_STRICT_MSGPACK=true" "$postgres_bootstrap_script"
grep -Fq "scripts/local/find_free_port.py" "$test_postgres_runner"
grep -Fq "docker compose" "$test_postgres_runner"
! grep -R -Fq "rg-langgraph-ora-foundry-public-dev2" \
  "$root_dir/Makefile" "$root_dir/scripts/foundry" "$root_dir/infra/foundry-hosted/iac" "$root_dir/deployment"

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
  FOUNDRY_HOSTED_RESPONSES_URL FOUNDRY_MODEL_DEPLOYMENT_NAME \
  FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME FOUNDRY_EVAL_MODEL HOSTED_AGENT_NAME \
  FOUNDRY_RUNTIME_CONNECTION_NAME \
  AZURE_OPENAI_ENDPOINT AZURE_CONTAINER_REGISTRY_NAME \
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
