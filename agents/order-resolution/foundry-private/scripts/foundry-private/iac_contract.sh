#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
source "$SCRIPT_DIR/common.sh"

template="$PRIVATE_AZD_DIR/iac/main.bicep"
private_require_command az
private_require_file "$template"

az bicep build --file "$template" --stdout >/dev/null

required_patterns=(
  "Microsoft.Compute/virtualMachines"
  "Microsoft.Network/privateEndpoints"
  "Microsoft.CognitiveServices/accounts/projects/capabilityHosts"
  "publicNetworkAccess: 'Disabled'"
  "PRIVATE_RUNNER_VM_NAME"
)
for pattern in "${required_patterns[@]}"; do
  grep -Fq "$pattern" "$template" ||
    private_die "private infrastructure contract is incomplete: missing $pattern in $template"
done

for prohibited_pattern in \
  "publicNetworkAccess: 'Enabled'" \
  "publicNetworkAccessForIngestion: 'Enabled'" \
  "publicNetworkAccessForQuery: 'Enabled'" \
  "allow-all-temporary" \
  "startIpAddress: '0.0.0.0'" \
  "POSTGRES_OPERATOR_IP" \
  "publicIPAddress:"; do
  if grep -Fq "$prohibited_pattern" "$template"; then
    private_die "private infrastructure contract forbids $prohibited_pattern in $template"
  fi
done

grep -Fq "resource backendContainerAppBootstrap" "$template" ||
  private_die "private infrastructure contract is missing the backend Container App"
grep -Fq "resource frontendContainerAppBootstrap" "$template" ||
  private_die "private infrastructure contract is missing the frontend Container App"
grep -Fq "external: false" "$template" ||
  private_die "private infrastructure contract requires internal backend ingress"
grep -Fq "external: true" "$template" ||
  private_die "private infrastructure contract requires the intended frontend-only ingress"
grep -Fq "purpose: 'runner-egress-only'" "$template" ||
  private_die "private runner requires explicit outbound-only NAT"
grep -Fq "targetPort: 8000" "$template" ||
  private_die "private backend ingress must target port 8000"
grep -Fq "targetPort: 5173" "$template" ||
  private_die "private frontend ingress must target port 5173"
grep -Fq "azureADAuthenticationAsArmPolicy" "$template" ||
  private_die "private ACR requires ARM-audience authentication for Foundry"
grep -Fq "category: 'ContainerRegistry'" "$template" ||
  private_die "private Foundry project requires a managed-identity ACR connection"
grep -Fq "projectContainerRegistryConnectionBootstrap" "$template" ||
  private_die "private Foundry project ACR connection must be deployment ordered"
if grep -Fq "Order Resolution Private ACR Pull Assigner" "$template"; then
  private_die "private runner must not manage per-version hosted ACR assignments"
fi
grep -Fq "resource projectStorageBlobDataContributorBootstrap" "$template" ||
  private_die "private Standard Agent setup requires account-scoped Storage Blob Data Contributor"
grep -Fq "StringLikeIgnoreCase \\'*-azureml-agent\\'" \
  "$PRIVATE_AZD_DIR/iac/modules/standard-agent-data-role-assignments.bicep" ||
  private_die "private Standard Agent setup requires the workspace-scoped Storage Blob Data Owner condition"
grep -Fq "param standardAgentSearchLocation string = 'westus3'" "$template" ||
  private_die "private Search must avoid the documented East US 2 capacity constraint"
grep -Fq "location: standardAgentSearchLocation" "$template" ||
  private_die "private Search resource and connection must use the approved Search region"
grep -Fq "searchPrivateVnetAddressSpace = '10.75.0.0/24'" "$template" ||
  private_die "private Search requires a same-region secondary VNet"
grep -Fq "privateToSearchVnetPeeringBootstrap" "$template" ||
  private_die "private Search VNet must be globally peered to the primary lane VNet"
grep -Fq "id: searchPrivateEndpointSubnetBootstrap!.id" "$template" ||
  private_die "private Search endpoint must use its same-region subnet"
grep -Fq "var isFoundryReadyPhase = isBootstrap && deployFoundryReadyResources" "$template" ||
  private_die "Foundry endpoint and project resources require the explicit readiness phase"
grep -Fq "var isFoundryConvergencePhase = isBootstrap && !deployFoundryReadyResources" "$template" ||
  private_die "Foundry account mutation must be isolated to the convergence phase"
grep -Fq "parent: foundryAccountRoleScope" "$template" ||
  private_die "Foundry-ready resources must bind to the existing account without issuing another account PUT"

echo "Private Bicep contract passed."
