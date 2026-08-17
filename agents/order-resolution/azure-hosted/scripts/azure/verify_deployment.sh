#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

for command in az curl jq; do
  require_command "$command"
done
assert_target

subscription_id="$(required_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(required_azd_value AZURE_RESOURCE_GROUP)"
backend_name="$(required_azd_value BACKEND_CONTAINER_APP_NAME)"
frontend_name="$(required_azd_value FRONTEND_CONTAINER_APP_NAME)"
postgres_name="$(required_azd_value POSTGRES_SERVER_NAME)"
postgres_fqdn="$(required_azd_value POSTGRES_SERVER_FQDN)"
foundry_project_endpoint="$(required_azd_value AZURE_AI_PROJECT_ENDPOINT)"
evidence_dir="$(release_evidence_dir)"
images_file="$evidence_dir/images.json"
expected_backend="$(jq -er '.backend_image' "$images_file")"
expected_frontend="$(jq -er '.frontend_image' "$images_file")"

container_apps_json="$(
  az containerapp list \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    -o json
)"
jq -e \
  --arg backend "$backend_name" \
  --arg frontend "$frontend_name" \
  '([.[].name] | sort) == ([$backend, $frontend] | sort)' \
  <<<"$container_apps_json" >/dev/null || {
    echo "Target resource group must contain exactly the expected backend and frontend Container Apps." >&2
    exit 1
  }

backend_json="$(az containerapp show --subscription "$subscription_id" --resource-group "$resource_group" --name "$backend_name" -o json)"
frontend_json="$(az containerapp show --subscription "$subscription_id" --resource-group "$resource_group" --name "$frontend_name" -o json)"
[[ "$(jq -r '.properties.configuration.ingress.external' <<<"$backend_json")" == "false" ]]
[[ "$(jq -r '.properties.configuration.ingress.external' <<<"$frontend_json")" == "true" ]]
[[ "$(jq -r '.properties.template.containers[0].image' <<<"$backend_json")" == "$expected_backend" ]]
[[ "$(jq -r '.properties.template.containers[0].image' <<<"$frontend_json")" == "$expected_frontend" ]]
[[ "$(jq -r '[.properties.template.containers[0].env[] | select(.name=="RUNTIME_TARGET") | .value][0]' <<<"$backend_json")" == "direct_langgraph" ]]
[[ "$(jq -r '.properties.template.scale.maxReplicas' <<<"$backend_json")" == "1" ]] || {
  echo "Backend max replicas must remain 1 until distributed HITL admission locking exists." >&2
  exit 1
}
! grep -q 'azure.ai.agent' <<<"$backend_json"
! grep -q 'host: azure.ai.agent' "$ROOT_DIR/azure.yaml"

hosted_agents_json="$(
  az rest \
    --method GET \
    --url "${foundry_project_endpoint%/}/agents?api-version=2025-05-15-preview" \
    --resource "https://ai.azure.com" \
    -o json
)"
hosted_agent_count="$(jq -er '(.value // .data // []) | length' <<<"$hosted_agents_json")"
[[ "$hosted_agent_count" == "0" ]] || {
  echo "Foundry project contains an agent application/version leg; this lane requires none." >&2
  exit 1
}

postgres_json="$(
  az postgres flexible-server show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$postgres_name" \
    -o json
)"
[[ "$(jq -r '.name' <<<"$postgres_json")" == "$postgres_name" ]]
[[ "$(jq -r '.fullyQualifiedDomainName // .properties.fullyQualifiedDomainName' <<<"$postgres_json")" == "$postgres_fqdn" ]]
[[ "$(jq -r '.authConfig.activeDirectoryAuth // .properties.authConfig.activeDirectoryAuth' <<<"$postgres_json")" == "Enabled" ]]
[[ "$(jq -r '.authConfig.passwordAuth // .properties.authConfig.passwordAuth' <<<"$postgres_json")" == "Enabled" ]]
[[ "$(jq -r '.network.publicNetworkAccess // .properties.network.publicNetworkAccess' <<<"$postgres_json")" == "Enabled" ]]

firewall_json="$(
  az postgres flexible-server firewall-rule list \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --server-name "$postgres_name" \
    -o json
)"
jq -e '
  any(.[];
    .name == "public-poc-allow-azure-services"
    and .startIpAddress == "0.0.0.0"
    and .endIpAddress == "0.0.0.0"
  )
' <<<"$firewall_json" >/dev/null

require_secure_transport="$(
  az postgres flexible-server parameter show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --server-name "$postgres_name" \
    --name require_secure_transport \
    --query value -o tsv
)"
[[ "${require_secure_transport,,}" == "on" ]]

frontend_fqdn="$(jq -r '.properties.configuration.ingress.fqdn' <<<"$frontend_json")"
curl -fsS --max-time 60 "https://${frontend_fqdn}/health" | grep -Fxq ok
curl -fsS --max-time 60 "https://${frontend_fqdn}/api/health" | jq -e '.status == "ok"' >/dev/null

jq -n \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg frontend_url "https://${frontend_fqdn}" \
  --arg postgres_server "$postgres_name" \
  '{status:"passed",generated_at:$generated_at,backend_external:false,backend_max_replicas:1,frontend_external:true,frontend_url:$frontend_url,same_origin_proxy:true,container_app_count:2,hosted_agent_applications:0,hosted_agent_versions:0,postgres_server:$postgres_server,postgres_dual_auth:true,postgres_tls_required:true,postgres_network_posture:"public-poc-azure-services-firewall"}' \
  >"$evidence_dir/verification.json"
