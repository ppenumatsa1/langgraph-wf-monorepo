#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

for command in az azd jq mktemp; do
  private_require_command "$command"
done

dry_run=false
if [[ "${1:-}" == "--dry-run" && $# -eq 1 ]]; then
  dry_run=true
elif [[ $# -ne 0 ]]; then
  private_die "usage: reconcile_evaluation_storage.sh [--dry-run]"
fi

profile_path="${FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE:-}"
[[ -n "$profile_path" ]] ||
  private_die "FOUNDRY_PRIVATE_DEPLOYMENT_PROFILE is required for storage reconciliation"

"$SCRIPT_DIR/apply_profile.sh"
private_require_target
"$SCRIPT_DIR/bootstrap_env.sh"
[[ "$(private_azd_value INFRASTRUCTURE_MODE)" == "reuse" ]] ||
  private_die "targeted evaluation Storage reconciliation requires retained reuse mode"

subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(private_azd_value AZURE_RESOURCE_GROUP)"
location="$(private_azd_value AZURE_LOCATION)"
foundry_account="$(private_required_env_value FOUNDRY_ACCOUNT_NAME)"
foundry_project="$(private_required_env_value FOUNDRY_PROJECT_NAME)"
storage_name="$(private_required_env_value STANDARD_AGENT_STORAGE_ACCOUNT_NAME)"
storage_scope="/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.Storage/storageAccounts/${storage_name}"
project_url="https://management.azure.com/subscriptions/${subscription_id}/resourceGroups/${resource_group}/providers/Microsoft.CognitiveServices/accounts/${foundry_account}/projects/${foundry_project}"
connection_url="${project_url}/connections/private-storage?api-version=2025-04-01-preview"
storage_owner_role="/subscriptions/${subscription_id}/providers/Microsoft.Authorization/roleDefinitions/b7e6dc6d-f1e8-4753-8033-0f276bb0955b"
storage_blob_contributor_role="/subscriptions/${subscription_id}/providers/Microsoft.Authorization/roleDefinitions/ba92f5b4-2d11-453d-a403-e96b0029c9fe"
storage_account_contributor_role="/subscriptions/${subscription_id}/providers/Microsoft.Authorization/roleDefinitions/17d1049b-9a84-46fb-8f53-869881c3d3ab"
role_update_file=""

cleanup() {
  local status=$?
  trap - EXIT
  if [[ -n "$role_update_file" && -f "$role_update_file" ]]; then
    rm -f -- "$role_update_file"
  fi
  exit "$status"
}
trap cleanup EXIT

account_json="$(
  az cognitiveservices account show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$foundry_account" \
    --output json
)"
project_json="$(
  az rest \
    --subscription "$subscription_id" \
    --method get \
    --url "${project_url}?api-version=2025-06-01" \
    --output json
)"
account_principal="$(jq -r '.identity.principalId // empty' <<<"$account_json")"
project_principal="$(jq -r '.identity.principalId // empty' <<<"$project_json")"
workspace_id="$(jq -r '.properties.internalId // empty' <<<"$project_json")"
[[ "$account_principal" =~ ^[[:xdigit:]-]{36}$ ]] ||
  private_die "Foundry account managed identity is missing"
[[ "$project_principal" =~ ^[[:xdigit:]-]{36}$ ]] ||
  private_die "Foundry project managed identity is missing"
[[ "$workspace_id" =~ ^[[:xdigit:]]{32}$ ]] ||
  private_die "Foundry project raw workspace ID is invalid"

storage_json="$(
  az storage account show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$storage_name" \
    --output json
)"
storage_network_rules="$(
  jq -c '{
    ipRules: (.networkRuleSet.ipRules // []),
    virtualNetworkRules: (.networkRuleSet.virtualNetworkRules // []),
    resourceAccessRules: (.networkRuleSet.resourceAccessRules // [])
  }' <<<"$storage_json"
)"
jq -e '
  .publicNetworkAccess == "Disabled"
  and .networkRuleSet.defaultAction == "Deny"
  and .allowSharedKeyAccess == false
  and (.networkRuleSet.bypass == "None" or .networkRuleSet.bypass == "AzureServices")
' <<<"$storage_json" >/dev/null ||
  private_die "refusing to reconcile unexpected private Storage security posture"

assignments="$(
  az role assignment list \
    --subscription "$subscription_id" \
    --scope "$storage_scope" \
    --output json
)"

for identity in \
  "account:${account_principal}" \
  "project:${project_principal}"; do
  identity_kind="${identity%%:*}"
  principal_id="${identity#*:}"
  for required_role in \
    "$storage_blob_contributor_role" \
    "$storage_account_contributor_role"; do
    count="$(
      jq \
        --arg principal "$principal_id" \
        --arg role "${required_role,,}" '
          [
            .[] |
            select(
              .principalId == $principal
              and (.roleDefinitionId | ascii_downcase) == $role
              and (.condition // null) == null
            )
          ] | length
        ' <<<"$assignments"
    )"
    [[ "$count" == "1" ]] ||
      private_die "Foundry ${identity_kind} identity requires exactly one unconditioned Contributor assignment"
  done
done

project_owner_count="$(
  jq \
    --arg principal "$project_principal" \
    --arg role "${storage_owner_role,,}" '
      [.[] | select(.principalId == $principal and (.roleDefinitionId | ascii_downcase) == $role)] | length
    ' <<<"$assignments"
)"
[[ "$project_owner_count" == "1" ]] ||
  private_die "Foundry project requires exactly one Storage Blob Data Owner assignment"
project_owner="$(
  jq -c \
    --arg principal "$project_principal" \
    --arg role "${storage_owner_role,,}" '
      .[] | select(.principalId == $principal and (.roleDefinitionId | ascii_downcase) == $role)
    ' <<<"$assignments"
)"

condition="((!(ActionMatches{'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/tags/read'}) AND !(ActionMatches{'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/filter/action'}) AND !(ActionMatches{'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/tags/write'})) OR (@Resource[Microsoft.Storage/storageAccounts/blobServices/containers:name] StringStartsWithIgnoreCase '${workspace_id}' AND @Resource[Microsoft.Storage/storageAccounts/blobServices/containers:name] StringLikeIgnoreCase '*-azureml-agent'))"
owner_description="Restrict Standard Agent ownership to this Foundry workspace agent containers."
current_project_condition="$(jq -r '.condition // empty' <<<"$project_owner")"
if [[ -n "$current_project_condition" && "$current_project_condition" != "$condition" ]]; then
  private_die "refusing to replace an unexpected Foundry project Owner condition"
fi
project_owner_id="$(jq -r '.id // empty' <<<"$project_owner")"
[[ "$project_owner_id" == "${storage_scope}/providers/Microsoft.Authorization/roleAssignments/"* ]] ||
  private_die "Foundry project Owner assignment has an unexpected scope"

current_project_description="$(jq -r '.description // empty' <<<"$project_owner")"
project_owner_requires_update=false
if [[ "$current_project_condition" != "$condition" || "$current_project_description" != "$owner_description" ]]; then
  project_owner_requires_update=true
fi

account_owner_id=""
account_owner_count="$(
  jq \
    --arg principal "$account_principal" \
    --arg role "${storage_owner_role,,}" '
      [.[] | select(.principalId == $principal and (.roleDefinitionId | ascii_downcase) == $role)] | length
    ' <<<"$assignments"
)"
[[ "$account_owner_count" == "0" || "$account_owner_count" == "1" ]] ||
  private_die "Foundry account has multiple unexpected Storage Blob Data Owner assignments"
if [[ "$account_owner_count" == "1" ]]; then
  account_owner="$(
    jq -c \
      --arg principal "$account_principal" \
      --arg role "${storage_owner_role,,}" '
        .[] | select(.principalId == $principal and (.roleDefinitionId | ascii_downcase) == $role)
      ' <<<"$assignments"
  )"
  [[ "$(jq -r '.condition // empty' <<<"$account_owner")" == "" ]] ||
    private_die "refusing to delete a conditioned Foundry account Owner assignment"
  account_owner_id="$(jq -r '.id // empty' <<<"$account_owner")"
  [[ "$account_owner_id" == "${storage_scope}/providers/Microsoft.Authorization/roleAssignments/"* ]] ||
    private_die "Foundry account Owner assignment has an unexpected scope"
fi

connection_json="$(
  az rest \
    --subscription "$subscription_id" \
    --method get \
    --url "$connection_url" \
    --output json
)"
storage_blob_endpoint="$(jq -r '.primaryEndpoints.blob // empty' <<<"$storage_json")"
[[ "$storage_blob_endpoint" == "https://${storage_name}.blob.core.windows.net/" ]] ||
  private_die "private Storage blob endpoint is unexpected"
jq -e \
  --arg target "$storage_blob_endpoint" \
  --arg storage_scope "$storage_scope" \
  --arg location "$location" '
    .properties.category == "AzureStorageAccount"
    and .properties.authType == "AAD"
    and .properties.target == $target
    and (.properties.metadata.ApiType // null) == "Azure"
    and (.properties.metadata.ResourceId // null) == $storage_scope
    and (.properties.metadata.location // null) == $location
    and ((.properties.metadata | keys | sort) == ["ApiType", "ResourceId", "location"])
    and .properties.isSharedToAll == false
    and .properties.sharedUserList == []
    and .properties.peRequirement == "NotRequired"
    and .properties.useWorkspaceManagedIdentity == false
    and .properties.group == "Azure"
  ' <<<"$connection_json" >/dev/null ||
  private_die "refusing to reconcile an unexpected private-storage connection"

if [[ "$dry_run" == "true" ]]; then
  printf 'Storage bypass: %s -> AzureServices\n' \
    "$(jq -r '.networkRuleSet.bypass' <<<"$storage_json")"
  printf 'Project Owner assignment: %s (%s)\n' \
    "$project_owner_id" \
    "$([[ "$project_owner_requires_update" == "true" ]] && printf 'condition update required' || printf 'already converged')"
  printf 'Project Owner assignment name: %s\n' \
    "$(jq -r '.name' <<<"$project_owner")"
  printf 'Account Owner assignment: %s\n' \
    "${account_owner_id:-none; no deletion required}"
  printf 'Project connection: private-storage (%s; already converged, validation only)\n' \
    "$(jq -r '.properties.target' <<<"$connection_json")"
  echo "Dry run completed without Azure mutation."
  exit 0
fi

if [[ "$project_owner_requires_update" == "true" ]]; then
  role_update_file="$(mktemp --suffix=.json)"
  jq \
    --arg condition "$condition" \
    --arg description "$owner_description" '
      .condition = $condition
      | .conditionVersion = "2.0"
      | .description = $description
    ' <<<"$project_owner" >"$role_update_file"
  az role assignment update \
    --subscription "$subscription_id" \
    --role-assignment "$role_update_file" \
    --output none
fi

az storage account update \
  --subscription "$subscription_id" \
  --resource-group "$resource_group" \
  --name "$storage_name" \
  --bypass AzureServices \
  --default-action Deny \
  --output none

final_storage="$(
  az storage account show \
    --subscription "$subscription_id" \
    --resource-group "$resource_group" \
    --name "$storage_name" \
    --output json
)"
jq -e '
  .publicNetworkAccess == "Disabled"
  and .networkRuleSet.defaultAction == "Deny"
  and .networkRuleSet.bypass == "AzureServices"
  and .allowSharedKeyAccess == false
' <<<"$final_storage" >/dev/null ||
  private_die "private Storage posture did not converge"
[[ "$(
  jq -c '{
    ipRules: (.networkRuleSet.ipRules // []),
    virtualNetworkRules: (.networkRuleSet.virtualNetworkRules // []),
    resourceAccessRules: (.networkRuleSet.resourceAccessRules // [])
  }' <<<"$final_storage"
)" == "$storage_network_rules" ]] ||
  private_die "private Storage network rules changed unexpectedly"

final_connection="$(
  az rest \
    --subscription "$subscription_id" \
    --method get \
    --url "$connection_url" \
    --output json
)"
jq -e \
  --arg target "$storage_blob_endpoint" \
  --arg storage_scope "$storage_scope" \
  --arg location "$location" '
    .properties.category == "AzureStorageAccount"
    and .properties.authType == "AAD"
    and .properties.target == $target
    and .properties.metadata == {
      ApiType: "Azure",
      ResourceId: $storage_scope,
      location: $location
    }
    and .properties.isSharedToAll == false
    and .properties.sharedUserList == []
    and .properties.peRequirement == "NotRequired"
    and .properties.useWorkspaceManagedIdentity == false
    and .properties.group == "Azure"
  ' <<<"$final_connection" >/dev/null ||
  private_die "private-storage connection did not converge"

if [[ -n "$account_owner_id" ]]; then
  az role assignment delete \
    --subscription "$subscription_id" \
    --ids "$account_owner_id"
fi

for attempt in {1..6}; do
  final_assignments="$(
    az role assignment list \
      --subscription "$subscription_id" \
      --scope "$storage_scope" \
      --output json
  )"
  if jq -e \
    --arg account "$account_principal" \
    --arg project "$project_principal" \
    --arg owner "${storage_owner_role,,}" \
    --arg condition "$condition" \
    --arg description "$owner_description" '
      ([.[] | select(.principalId == $account and (.roleDefinitionId | ascii_downcase) == $owner)] | length) == 0
      and (
        [.[] | select(
          .principalId == $project
          and (.roleDefinitionId | ascii_downcase) == $owner
          and .conditionVersion == "2.0"
          and .condition == $condition
          and .description == $description
        )] | length
      ) == 1
    ' <<<"$final_assignments" >/dev/null; then
    break
  fi
  [[ "$attempt" -lt 6 ]] || private_die "private Storage Owner assignments did not converge"
  sleep 10
done

private_azd_set INFRASTRUCTURE_MODE reuse
echo "Private Foundry evaluation Storage reconciliation completed."
