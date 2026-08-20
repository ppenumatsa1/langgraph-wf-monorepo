#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

[[ "$1" == "acr_package" ]] || private_die "ACR package stage mismatch"
for command in az cp docker find git jq tar; do
  private_require_command "$command"
done
private_require_target
private_assert_clean_source

subscription_id="$(private_azd_value AZURE_SUBSCRIPTION_ID)"
resource_group="$(private_azd_value AZURE_RESOURCE_GROUP)"
registry_name="$(private_required_env_value AZURE_CONTAINER_REGISTRY_NAME)"
registry_endpoint="$(private_required_env_value AZURE_CONTAINER_REGISTRY_ENDPOINT)"
backend_repository="$(private_required_env_value BACKEND_IMAGE_REPOSITORY)"
frontend_repository="$(private_required_env_value FRONTEND_IMAGE_REPOSITORY)"
registry_json="$(az acr show --subscription "$subscription_id" --resource-group "$resource_group" --name "$registry_name" --output json)"

[[ "$(jq -r '.sku.name // empty' <<<"$registry_json")" == "Premium" ]] ||
  private_die "private ACR must use the Premium SKU"
[[ "$(jq -r '.properties.publicNetworkAccess // .publicNetworkAccess // empty' <<<"$registry_json")" == "Disabled" ]] ||
  private_die "private ACR public network access must be Disabled"
[[ "$(jq -r '.adminUserEnabled // .properties.adminUserEnabled // empty' <<<"$registry_json")" == "false" ]] ||
  private_die "private ACR admin user must be disabled"
connections="$(az network private-endpoint-connection list --id "$(jq -r '.id' <<<"$registry_json")" --output json)"
jq -e 'any(.[]; (.privateLinkServiceConnectionState.status // "") == "Approved")' \
  <<<"$connections" >/dev/null ||
  private_die "private ACR needs an approved private endpoint connection"

package_root="$PRIVATE_ROOT_DIR/.artifacts/private-packages/$(private_release_id)"
backend_context="$package_root/backend-release"
frontend_context="$package_root/frontend-release"
hosted_package_dir="$package_root/agent"

copy_sanitized_tree() {
  local source_dir="$1"
  local destination_dir="$2"
  rm -rf -- "$destination_dir"
  mkdir -p "$destination_dir"
  tar \
    --exclude='.env*' \
    --exclude='.venv' \
    --exclude='.foundry' \
    --exclude='.tmp' \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='dist' \
    --exclude='tests' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    -C "$source_dir" -cf - . |
    tar -C "$destination_dir" -xf -
  if find "$destination_dir" \( -type l -o -name '.env' -o -name '.env.*' -o -path '*/.foundry/*' \) -print -quit | grep -q .; then
    private_die "private ACR package context retained a link or secret-bearing runtime artifact"
  fi
}

copy_sanitized_tree "$PRIVATE_ROOT_DIR/backend" "$backend_context/backend"
mkdir -p "$backend_context/infra/foundry-hosted/runtime"
cp "$PRIVATE_AZD_DIR/runtime/Dockerfile.backend-release" \
  "$backend_context/infra/foundry-hosted/runtime/Dockerfile.backend-release"
cp "$PRIVATE_AZD_DIR/runtime/launch_backend.py" \
  "$backend_context/infra/foundry-hosted/runtime/launch_backend.py"
copy_sanitized_tree "$PRIVATE_ROOT_DIR/frontend" "$frontend_context"

PRIVATE_HOSTED_PACKAGE_DIR="$hosted_package_dir" "$SCRIPT_DIR/sync_hosted_source.sh"
commit="$(git -C "$PRIVATE_ROOT_DIR" rev-parse HEAD)"
image_tag="${commit:0:12}-$(date -u +%Y%m%d%H%M%S)"
az acr login --subscription "$subscription_id" --name "$registry_name" --output none
logout_registry() {
  docker logout "$registry_endpoint" >/dev/null 2>&1 || true
}
trap logout_registry EXIT

build_image() {
  local component="$1"
  local repository="$2"
  local dockerfile="$3"
  local context="$4"
  local digest image
  local tagged_image="${registry_endpoint}/${repository}:${image_tag}"
  docker build --file "$dockerfile" --tag "$tagged_image" "$context" >/dev/null
  docker push "$tagged_image" >/dev/null
  digest="$(az acr repository show --subscription "$subscription_id" --name "$registry_name" --image "${repository}:${image_tag}" --query digest --output tsv)"
  [[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]] ||
    private_die "$component ACR image did not resolve to an immutable digest"
  image="${registry_endpoint}/${repository}@${digest}"
  printf '%s' "$image"
}

backend_image="$(build_image backend "$backend_repository" "$backend_context/infra/foundry-hosted/runtime/Dockerfile.backend-release" "$backend_context")"
frontend_image="$(build_image frontend "$frontend_repository" "$frontend_context/Dockerfile" "$frontend_context")"
hosted_image="$(build_image hosted_agent order-resolution-private-hosted "$hosted_package_dir/Dockerfile" "$hosted_package_dir")"
logout_registry
trap - EXIT

private_azd_set PRIVATE_BACKEND_IMAGE "$backend_image"
private_azd_set PRIVATE_FRONTEND_IMAGE "$frontend_image"
private_azd_set PRIVATE_HOSTED_IMAGE "$hosted_image"

jq -n \
  --arg commit "$commit" \
  --arg backend "$backend_image" \
  --arg frontend "$frontend_image" \
  --arg hosted_agent "$hosted_image" \
  '{source_commit:$commit,images:{backend:$backend,frontend:$frontend,hosted_agent:$hosted_agent},acr_public_network_access:"Disabled"}'
