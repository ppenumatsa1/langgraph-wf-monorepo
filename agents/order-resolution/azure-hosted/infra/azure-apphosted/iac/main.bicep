targetScope = 'subscription'

@description('Only this subscription may receive the Azure-hosted lane.')
@allowed([
  '7df95e88-701c-4693-af77-3159f83b558d'
])
param targetSubscriptionId string = '7df95e88-701c-4693-af77-3159f83b558d'

@description('Only this resource group may receive the Azure-hosted lane.')
@allowed([
  'rg-langgraph-ora-azure-hosted'
])
param targetResourceGroupName string = 'rg-langgraph-ora-azure-hosted'

@description('Azure region for the public POC.')
@allowed([
  'eastus2'
])
param location string = 'eastus2'

@allowed([
  'bootstrap'
  'reuse'
])
@description('bootstrap creates the lane once; reuse is a non-mutating target validation mode.')
param infrastructureMode string = 'bootstrap'

@minLength(3)
@maxLength(15)
param namePrefix string = 'orderresolution'

@description('Object ID of the Entra principal that owns PostgreSQL DDL.')
param postgresAdministratorObjectId string

@description('Display name of the Entra principal that owns PostgreSQL DDL.')
param postgresAdministratorPrincipalName string

@description('Local bootstrap login required by PostgreSQL server creation. It is not used by the application runtime.')
param postgresServerAdministratorLogin string = 'pgbootstrapadmin'

@secure()
@description('Generated bootstrap password stored only in the local AZD environment.')
param postgresServerAdministratorPassword string

@allowed([
  'User'
  'ServicePrincipal'
  'Group'
])
param postgresAdministratorPrincipalType string = 'User'

@description('Optional public IPv4 address used only by the administrator for schema/bootstrap work.')
param postgresOperatorIp string = ''

param tags object = {
  workload: 'order-resolution'
  lane: 'azure-hosted'
  environment: 'poc'
}

var suffix = uniqueString(targetSubscriptionId, targetResourceGroupName, namePrefix)
var acrName = take('${toLower(namePrefix)}${suffix}acr', 50)
var logAnalyticsName = take('${namePrefix}-${suffix}-log', 63)
var appInsightsName = take('${namePrefix}-${suffix}-appi', 64)
var containerAppsEnvironmentName = take('${namePrefix}-${suffix}-cae', 32)
var backendName = take('${namePrefix}-${suffix}-api', 32)
var frontendName = take('${namePrefix}-${suffix}-web', 32)
var backendIdentityName = take('${namePrefix}-${suffix}-api-mi', 128)
var frontendIdentityName = take('${namePrefix}-${suffix}-web-mi', 128)
var postgresName = take('${toLower(namePrefix)}${suffix}pg', 63)
var foundryAccountName = take('${toLower(namePrefix)}${suffix}ai', 24)
var foundryProjectName = 'order-resolution'

resource targetResourceGroup 'Microsoft.Resources/resourceGroups@2024-03-01' = if (infrastructureMode == 'bootstrap') {
  name: targetResourceGroupName
  location: location
  tags: tags
}

module observability './modules/observability.bicep' = if (infrastructureMode == 'bootstrap') {
  name: 'observability-${suffix}'
  scope: resourceGroup(targetSubscriptionId, targetResourceGroupName)
  params: {
    location: location
    logAnalyticsWorkspaceName: logAnalyticsName
    applicationInsightsName: appInsightsName
    tags: tags
  }
  dependsOn: [
    targetResourceGroup
  ]
}

module registry './modules/registry.bicep' = if (infrastructureMode == 'bootstrap') {
  name: 'registry-${suffix}'
  scope: resourceGroup(targetSubscriptionId, targetResourceGroupName)
  params: {
    location: location
    containerRegistryName: acrName
    tags: tags
  }
  dependsOn: [
    targetResourceGroup
  ]
}

module foundry './modules/foundry.bicep' = if (infrastructureMode == 'bootstrap') {
  name: 'foundry-${suffix}'
  scope: resourceGroup(targetSubscriptionId, targetResourceGroupName)
  params: {
    location: location
    foundryAccountName: foundryAccountName
    foundryProjectName: foundryProjectName
    applicationInsightsName: appInsightsName
    tags: tags
  }
  dependsOn: [
    observability
  ]
}

module postgres './modules/postgres.bicep' = if (infrastructureMode == 'bootstrap') {
  name: 'postgres-${suffix}'
  scope: resourceGroup(targetSubscriptionId, targetResourceGroupName)
  params: {
    location: location
    postgresServerName: postgresName
    postgresDatabaseName: 'order_resolution'
    serverAdministratorLogin: postgresServerAdministratorLogin
    serverAdministratorPassword: postgresServerAdministratorPassword
    administratorObjectId: postgresAdministratorObjectId
    administratorPrincipalName: postgresAdministratorPrincipalName
    administratorPrincipalType: postgresAdministratorPrincipalType
    operatorIp: postgresOperatorIp
    tags: tags
  }
  dependsOn: [
    targetResourceGroup
  ]
}

module apps './modules/container-apps.bicep' = if (infrastructureMode == 'bootstrap') {
  name: 'apps-${suffix}'
  scope: resourceGroup(targetSubscriptionId, targetResourceGroupName)
  params: {
    location: location
    containerAppsEnvironmentName: containerAppsEnvironmentName
    logAnalyticsWorkspaceName: logAnalyticsName
    applicationInsightsName: appInsightsName
    containerRegistryName: acrName
    backendContainerAppName: backendName
    frontendContainerAppName: frontendName
    backendManagedIdentityName: backendIdentityName
    frontendManagedIdentityName: frontendIdentityName
    foundryAccountName: foundryAccountName
    foundryProjectName: foundryProjectName
    foundryModelDeploymentName: 'order-resolution-gpt-4-1-mini'
    tags: tags
  }
  dependsOn: [
    observability
    registry
    foundry
  ]
}

output AZURE_SUBSCRIPTION_ID string = targetSubscriptionId
output AZURE_RESOURCE_GROUP string = targetResourceGroupName
output AZURE_LOCATION string = location
output AZURE_CONTAINER_REGISTRY_NAME string = acrName
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = '${acrName}.azurecr.io'
output LOG_ANALYTICS_WORKSPACE_NAME string = logAnalyticsName
output APPLICATION_INSIGHTS_NAME string = appInsightsName
output CONTAINER_APPS_ENVIRONMENT_NAME string = containerAppsEnvironmentName
output BACKEND_CONTAINER_APP_NAME string = backendName
output FRONTEND_CONTAINER_APP_NAME string = frontendName
output PUBLIC_BACKEND_MANAGED_IDENTITY_NAME string = backendIdentityName
output PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME string = frontendIdentityName
output BACKEND_IMAGE_REPOSITORY string = 'order-resolution-azure-backend'
output FRONTEND_IMAGE_REPOSITORY string = 'order-resolution-azure-frontend'
output POSTGRES_SERVER_NAME string = postgresName
output POSTGRES_SERVER_FQDN string = '${postgresName}.postgres.database.azure.com'
output POSTGRES_DATABASE string = 'order_resolution'
output FOUNDRY_ACCOUNT_NAME string = foundryAccountName
output FOUNDRY_PROJECT_NAME string = foundryProjectName
output FOUNDRY_MODEL_DEPLOYMENT_NAME string = 'order-resolution-gpt-4-1-mini'
output FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME string = 'order-resolution-text-embedding-3-small'
output FOUNDRY_EVAL_MODEL string = 'order-resolution-gpt-4-1-mini-evaluation'
output AZURE_AI_PROJECT_ENDPOINT string = 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${foundryProjectName}'
output FOUNDRY_PROJECTS_ENDPOINT string = 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${foundryProjectName}'
