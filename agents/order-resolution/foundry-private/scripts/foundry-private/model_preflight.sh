#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

for command in az jq; do
  private_require_command "$command"
done
private_require_target
release_id="$(private_release_id)"

subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(private_azd_value AZURE_RESOURCE_GROUP)"
location="$(private_azd_value AZURE_LOCATION)"
account_name="$(private_required_env_value FOUNDRY_ACCOUNT_NAME)"
chat_deployment="$(private_required_env_value FOUNDRY_MODEL_DEPLOYMENT_NAME)"
embeddings_deployment="$(private_required_env_value FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME)"
evaluation_deployment="$(private_required_env_value FOUNDRY_EVAL_MODEL)"

for deployment in "$chat_deployment" "$embeddings_deployment" "$evaluation_deployment"; do
  [[ "$deployment" == order-resolution-private-* ]] ||
    private_die "private model deployment name must begin with order-resolution-private-"
done

deployments="$(az cognitiveservices account deployment list --subscription "$subscription_id" --resource-group "$resource_group" --name "$account_name" --output json)"
usage="$(az cognitiveservices usage list --subscription "$subscription_id" --location "$location" --output json)"

verify_deployment() {
  local purpose="$1"
  local deployment_name="$2"
  local deployment model capacity state quota quota_current quota_limit
  deployment="$(jq -cer --arg name "$deployment_name" '[.[] | select(.name == $name)] | if length == 1 then .[0] else error("expected exactly one deployment") end' <<<"$deployments")" ||
    private_die "expected exactly one private $purpose model deployment"
  model="$(jq -r '.properties.model.name // .model.name // empty' <<<"$deployment")"
  capacity="$(jq -r '.sku.capacity // 0' <<<"$deployment")"
  state="$(jq -r '.properties.provisioningState // .provisioningState // empty' <<<"$deployment")"
  [[ "${state,,}" == "succeeded" && -n "$model" && "$capacity" =~ ^[0-9]+$ && "$capacity" -gt 0 ]] ||
    private_die "private $purpose deployment is not provisioned with usable capacity"
  quota="$(jq -cer --arg model "${model,,}" '
    [
      .[]
      | select(
          (((.name.value // "") + " " + (.name.localizedValue // "")) | ascii_downcase)
          | contains($model)
        )
    ]
    | if length > 0 then .[0] else error("quota record missing") end
  ' <<<"$usage")" ||
    private_die "regional quota record is missing for private $purpose model $model"
  quota_current="$(jq -r '.currentValue // .current // empty' <<<"$quota")"
  quota_limit="$(jq -r '.limit // empty' <<<"$quota")"
  [[ "$quota_current" =~ ^[0-9]+$ && "$quota_limit" =~ ^[0-9]+$ && "$quota_current" -le "$quota_limit" ]] ||
    private_die "private $purpose model quota is exhausted or malformed"
  jq -n \
    --arg purpose "$purpose" \
    --arg deployment "$deployment_name" \
    --arg model "$model" \
    --argjson capacity "$capacity" \
    --argjson quota_current "$quota_current" \
    --argjson quota_limit "$quota_limit" \
    '{purpose:$purpose,deployment:$deployment,model:$model,capacity:$capacity,quota:{current:$quota_current,limit:$quota_limit,available:($quota_limit - $quota_current)}}'
}

models="$(
  jq -n \
    --argjson chat "$(verify_deployment chat "$chat_deployment")" \
    --argjson embeddings "$(verify_deployment embeddings "$embeddings_deployment")" \
    --argjson evaluation "$(verify_deployment evaluation "$evaluation_deployment")" \
    '[$chat,$embeddings,$evaluation]'
)"

jq -n \
  --arg release_id "$release_id" \
  --arg generated_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg subscription_id "$subscription_id" \
  --arg resource_group "$resource_group" \
  --arg location "$location" \
  --arg account_name "$account_name" \
  --argjson deployments "$models" \
  '{schema_version:1,evidence_type:"model_preflight",status:"passed",release_id:$release_id,generated_at:$generated_at,target:{subscription_id:$subscription_id,resource_group:$resource_group,location:$location,foundry_account:$account_name},deployments:$deployments,quota_checked:true,mutation_performed:false}' |
  python3 "$SCRIPT_DIR/write_artifact.py" --release-id "$release_id" --relative-path evidence/model-preflight.json
