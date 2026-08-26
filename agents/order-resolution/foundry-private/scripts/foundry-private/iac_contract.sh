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
grep -Fq "foundryVnetAddressSpace = '10.76.0.0/16'" "$template" ||
  private_die "Foundry network injection requires the dedicated recovery VNet"
grep -Fq "foundryPrivateEndpointSubnetPrefix = '10.76.1.0/24'" "$template" ||
  private_die "Foundry-hosted compute requires a dedicated dependency endpoint subnet"
grep -Fq "privateToFoundryVnetPeeringBootstrap" "$template" ||
  private_die "the application VNet must be peered to the Foundry VNet"
grep -Fq "foundryToPrivateVnetPeeringBootstrap" "$template" ||
  private_die "the Foundry VNet must be peered to the application VNet"
grep -Fq "foundryContainerRegistryPrivateEndpointBootstrap" "$template" ||
  private_die "Foundry-hosted compute requires a private path to the lane-owned registry"
grep -Fq "foundryStoragePrivateEndpointBootstrap" "$template" ||
  private_die "Foundry-hosted compute requires a private path to lane-owned storage"
grep -Fq "foundryCosmosPrivateEndpointBootstrap" "$template" ||
  private_die "Foundry-hosted compute requires a private path to lane-owned Cosmos DB"
grep -Fq "foundrySearchPrivateEndpointBootstrap" "$template" ||
  private_die "Foundry-hosted compute requires a private path to lane-owned AI Search"
grep -Fq "targetPort: 8000" "$template" ||
  private_die "private backend ingress must target port 8000"
grep -Fq "targetPort: 5173" "$template" ||
  private_die "private frontend ingress must target port 5173"
grep -Fq "azureADAuthenticationAsArmPolicy" "$template" ||
  private_die "private ACR requires ARM-audience authentication for Foundry"
if grep -Fq "projectContainerRegistryConnectionBootstrap" "$template"; then
  private_die "private Foundry ACR access must use project identity RBAC, not a project connection"
fi
grep -Fq "resource projectApplicationInsightsConnectionBootstrap" "$template" ||
  private_die "private Foundry telemetry requires a project-scoped Application Insights connection"
grep -Fq "isSharedToAll: false" "$template" ||
  private_die "private Foundry telemetry connection must not be shared across projects"
grep -Fq "resource foundryAccountDiagnosticsBootstrap" "$template" ||
  private_die "private Foundry account must emit diagnostics to the private workspace"
grep -Fq "category: 'Audit'" "$template" ||
  private_die "private Foundry diagnostics must include audit events"
grep -Fq "category: 'Trace'" "$template" ||
  private_die "private Foundry diagnostics must include service traces"
if grep -Fq "category: 'RequestResponse'" "$template"; then
  private_die "private Foundry diagnostics must not enable request/response content capture"
fi
if grep -Fq "Order Resolution Private ACR Pull Assigner" "$template"; then
  private_die "private runner must not manage per-version hosted ACR assignments"
fi
grep -Fq "resource projectStorageBlobDataContributorBootstrap" "$template" ||
  private_die "private Standard Agent setup requires project Storage Blob Data Contributor"
grep -Fq "bypass: 'AzureServices'" "$template" ||
  private_die "private Foundry evaluation storage requires the trusted Azure-services bypass"
grep -Fq "param foundryRaiPolicyName string = 'Microsoft.DefaultV2'" "$template" ||
  private_die "private Foundry model deployments must default to Microsoft.DefaultV2"
grep -Fq "projectStorageBlobDataContributorBootstrap" "$template" ||
  private_die "private storage connection must wait for project storage RBAC"
grep -Fq "accountStorageAccountContributorBootstrap" "$template" ||
  private_die "private convergence must provision account storage RBAC before the ready phase"
grep -Fq "projectWorkspaceId: projectWorkspaceId" "$template" ||
  private_die "private Standard Agent storage role assignment requires the raw Foundry workspace ID"
if grep -Fq "projectWorkspaceIdGuid" "$template"; then
  private_die "private Standard Agent storage role assignment must not hyphenate the workspace ID"
fi
data_roles_module="$PRIVATE_AZD_DIR/iac/modules/standard-agent-data-role-assignments.bicep"
grep -Fq "resource projectStorageBlobDataOwner" "$data_roles_module" ||
  private_die "private Standard Agent setup requires project Storage Blob Data Owner"
grep -Fq "StringLikeIgnoreCase \\'*-azureml-agent\\'" "$data_roles_module" ||
  private_die "private Standard Agent Owner must remain scoped to agent containers"
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
