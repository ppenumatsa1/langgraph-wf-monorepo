#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
iac_dir="$(cd "$script_dir/.." && pwd -P)"
hosted_dir="$(cd "$iac_dir/.." && pwd -P)"
template="$iac_dir/main.bicep"
parameters="$iac_dir/main.parameters.json"
data_roles_module="$iac_dir/modules/standard-agent-data-role-assignments.bicep"
compiled_template="$iac_dir/.private-network-contract-$$.json"
trap 'rm -f "$compiled_template"' EXIT

az bicep build --file "$template" --outfile "$compiled_template"
az bicep build --file "$data_roles_module" --stdout >/dev/null

for expected in \
  "privateVnetAddressSpace = '10.74.0.0/16'" \
  "foundryVnetAddressSpace = '10.76.0.0/16'" \
  "foundryAgentSubnetPrefix = '10.76.0.0/24'" \
  "foundryPrivateEndpointSubnetPrefix = '10.76.1.0/24'" \
  "containerAppsSubnetPrefix = '10.74.2.0/23'" \
  "privateEndpointSubnetPrefix = '10.74.4.0/24'" \
  "privateRunnerSubnetPrefix = '10.74.5.0/27'" \
  "scenario: 'agent'" \
  "useMicrosoftManagedNetwork: false" \
  "foundryVnetBootstrap 'Microsoft.Network/virtualNetworks" \
  "privateToFoundryVnetPeeringBootstrap 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings" \
  "foundryToPrivateVnetPeeringBootstrap 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings" \
  "foundryStoragePrivateEndpointBootstrap 'Microsoft.Network/privateEndpoints" \
  "foundryCosmosPrivateEndpointBootstrap 'Microsoft.Network/privateEndpoints" \
  "foundrySearchPrivateEndpointBootstrap 'Microsoft.Network/privateEndpoints" \
  "foundryContainerRegistryPrivateEndpointBootstrap 'Microsoft.Network/privateEndpoints" \
  "privateRunnerVmBootstrap 'Microsoft.Compute/virtualMachines" \
  "privateRunnerNatGatewayBootstrap 'Microsoft.Network/natGateways" \
  "purpose: 'runner-egress-only'" \
  "privateRunnerReaderBootstrap 'Microsoft.Authorization/roleAssignments" \
  "privateRunnerContainerAppsContributorBootstrap 'Microsoft.Authorization/roleAssignments" \
  "privateRunnerFoundryProjectManagerBootstrap 'Microsoft.Authorization/roleAssignments" \
  "privateRunnerLogAnalyticsReaderBootstrap 'Microsoft.Authorization/roleAssignments" \
  "foundryAccountDiagnosticsBootstrap 'Microsoft.Insights/diagnosticSettings" \
  "category: 'Audit'" \
  "category: 'Trace'" \
  "category: 'ManagedNetworkEvent'" \
  "projectApplicationInsightsConnectionBootstrap 'Microsoft.CognitiveServices/accounts/projects/connections" \
  "privateRunnerDeploymentExecutorBootstrap 'Microsoft.Authorization/roleAssignments" \
  "privateRunnerBackendIdentityOperatorBootstrap 'Microsoft.Authorization/roleAssignments" \
  "privateRunnerFrontendIdentityOperatorBootstrap 'Microsoft.Authorization/roleAssignments" \
  "name: 'eadc314b-1a2d-4efa-be10-5d325db5065e'" \
  "projectCapabilityHostBootstrap 'Microsoft.CognitiveServices/accounts/projects/capabilityHosts" \
  "accountCapabilityHostName = '\${foundryAccountName}@aml_aiagentservice'" \
  "projectCosmosConnectionBootstrap" \
  "projectStorageConnectionBootstrap" \
  "projectSearchConnectionBootstrap" \
  "standardAgentDataRoleAssignmentsBootstrap" \
  "groupIds: [" \
  "'postgresqlServer'" \
  "publicNetworkAccess: 'Disabled'" \
  "publicNetworkAccessForIngestion: 'Disabled'" \
  "publicNetworkAccessForQuery: 'Disabled'" \
  "ingestionAccessMode: 'PrivateOnly'" \
  "queryAccessMode: 'PrivateOnly'"; do
  grep -Fq "$expected" "$template"
done

! grep -Fq "publicNetworkAccess: 'Enabled'" "$template"
! grep -Fq "category: 'RequestResponse'" "$template"
! grep -Fq "projectContainerRegistryConnectionBootstrap" "$template"
! grep -Fq "projectWorkspaceIdGuid" "$template"
! grep -Fq "resource containerRegistryPrivateEndpointBootstrap" "$template"
! grep -Fq "resource containerRegistryPrivateDnsZoneGroupBootstrap" "$template"
! grep -Fq 'POSTGRES_OPERATOR_IP' "$template"
grep -Fq "networkProfile:" "$template"
grep -Fq "id: privateRunnerNicBootstrap!.id" "$template"
! grep -Fq "publicIPAddress:" "$template"
grep -Fq "targetPort: 8000" "$template"
grep -Fq "targetPort: 5173" "$template"
! grep -Eqi 'manual.?approval|confirmation.?token' "$template"
! grep -Fq 'Microsoft.CognitiveServices/accounts/capabilityHosts@' "$template"

grep -Fq '"privateRunnerSshPublicKey"' "$parameters"
grep -Fq '${PRIVATE_RUNNER_SSH_PUBLIC_KEY}' "$parameters"
! grep -Fq 'POSTGRES_OPERATOR_IP' "$parameters"
! grep -Fq 'PUBLIC_BACKEND_MANAGED_IDENTITY_NAME' "$parameters"
! grep -Fq 'PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME' "$parameters"

grep -Fq 'host: azure.ai.agent' "$hosted_dir/azure.yaml"
grep -Fq '"publicNetworkAccess": "Disabled"' "$compiled_template"
grep -Fq '"postgresqlServer"' "$compiled_template"
grep -Fq "projectStorageBlobDataContributorBootstrap" "$template"
grep -Fq "name: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'" "$template"
grep -Fq "accountStorageBlobDataOwnerBootstrap" "$template"
grep -Fq "name: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'" "$template"
grep -Fq "scope: storageAccount" "$data_roles_module"
grep -Fq "projectStorageBlobDataOwner" "$data_roles_module"
! grep -Fq "condition:" "$data_roles_module"
grep -Fq '/dbs/enterprise_memory' "$data_roles_module"
