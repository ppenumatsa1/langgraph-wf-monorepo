targetScope = 'resourceGroup'

@allowed([
  'bootstrap'
  'reuse'
])
@description('bootstrap creates the complete lane. reuse references an already-created lane and creates no resources or role assignments.')
param infrastructureMode string = 'bootstrap'

@minLength(3)
@maxLength(20)
@description('Alphanumeric prefix used to derive deterministic bootstrap resource names.')
param namePrefix string

@description('Location for all public underwriting resources.')
param location string = resourceGroup().location

@description('Tags applied to resources created in bootstrap mode.')
param tags object = {}

@description('Foundry account name.')
param foundryAccountName string = take('${toLower(namePrefix)}${uniqueString(subscription().id, resourceGroup().id, namePrefix)}ai', 24)

@description('Foundry project name.')
param foundryProjectName string = 'underwriting'

@description('Foundry custom subdomain.')
param foundryCustomSubDomainName string = foundryAccountName

@description('Hosted agent name used to compose the Responses endpoint.')
param hostedAgentName string = 'underwriting-hosted'

@description('Foundry CustomKeys connection name for the hosted runtime database URL.')
param foundryRuntimeConnectionName string = 'underwritingruntimesecrets'

@description('Foundry chat deployment name.')
param foundryChatDeploymentName string = 'underwriting-gpt-4-1-mini'

@description('Foundry chat model format.')
param foundryChatModelFormat string = 'OpenAI'

@description('Foundry chat model name.')
param foundryChatModelName string = 'gpt-4.1-mini'

@description('Foundry chat model version.')
param foundryChatModelVersion string = '2025-04-14'

@description('Foundry chat deployment SKU.')
@allowed([
  'DataZoneStandard'
])
param foundryChatModelSkuName string = 'DataZoneStandard'

@minValue(1)
@description('Foundry chat deployment capacity in thousands of TPM.')
param foundryChatModelCapacity int = 1500

@description('Foundry embeddings deployment name.')
param foundryEmbeddingsDeploymentName string = 'underwriting-text-embedding-3-small'

@description('Foundry embeddings model version.')
param foundryEmbeddingsModelVersion string = '1'

@description('Foundry embeddings deployment capacity in thousands of TPM.')
param foundryEmbeddingsModelCapacity int = 120

@description('Foundry evaluator deployment name.')
param foundryEvaluationDeploymentName string = 'underwriting-gpt-4-1-mini-evaluation'

@description('Foundry evaluator deployment capacity in thousands of TPM.')
param foundryEvaluationModelCapacity int = 250

@description('Responsible AI policy used by Foundry model deployments.')
param foundryRaiPolicyName string = 'Microsoft.Default'

@description('Azure Container Registry name.')
param containerRegistryName string = take('${toLower(namePrefix)}${uniqueString(subscription().id, resourceGroup().id, namePrefix)}acr', 50)

@description('Log Analytics workspace name.')
param logAnalyticsWorkspaceName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-log', 63)

@description('Application Insights component name.')
param applicationInsightsName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-ai', 64)

@description('Container Apps environment name.')
param containerAppsEnvironmentName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-cae', 32)

@description('Internal backend Container App name.')
param backendContainerAppName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-backend', 32)

@description('External frontend Container App name.')
param frontendContainerAppName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-frontend', 32)

@description('User-assigned identity attached to the backend Container App.')
param publicBackendManagedIdentityName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-backend-mi', 128)

@description('User-assigned identity attached to the frontend Container App.')
param publicFrontendManagedIdentityName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-frontend-mi', 128)

@description('ACR repository written by the backend release.')
param backendImageRepository string = 'underwriting-public-backend'

@description('ACR repository written by the frontend release.')
param frontendImageRepository string = 'underwriting-public-frontend'

@description('Temporary public image used until the first backend release.')
param bootstrapBackendImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Temporary public image used until the first frontend release.')
param bootstrapFrontendImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('PostgreSQL Flexible Server name.')
param postgresServerName string = take('${toLower(namePrefix)}${uniqueString(subscription().id, resourceGroup().id, namePrefix)}pg', 63)

@description('PostgreSQL Flexible Server location.')
param postgresServerLocation string = location

@secure()
@description('PostgreSQL administrator password required only for bootstrap.')
param postgresAdministratorPassword string

@description('PostgreSQL administrator login.')
param postgresAdministratorLogin string = 'pgadmin'

@description('Public IPv4 address permitted to perform schema and credential setup.')
param postgresOperatorIp string

@description('Database used by the underwriting runtime.')
param postgresDatabaseName string = 'underwriting'

@description('PostgreSQL major version.')
param postgresVersion string = '17'

@description('PostgreSQL compute SKU.')
param postgresSkuName string = 'Standard_D2ds_v5'

@description('PostgreSQL compute tier.')
param postgresSkuTier string = 'GeneralPurpose'

@description('PostgreSQL storage size in GiB.')
param postgresStorageSizeGB int = 128

@description('PostgreSQL backup retention days.')
param postgresBackupRetentionDays int = 7

@allowed([
  'Enabled'
  'Disabled'
])
@description('PostgreSQL geo-redundant backup setting.')
param postgresGeoRedundantBackup string = 'Disabled'

@description('Dedicated storage account for Foundry evaluation artifacts.')
param evaluationStorageAccountName string = take('${toLower(namePrefix)}${uniqueString(subscription().id, resourceGroup().id, namePrefix)}eval', 24)

@secure()
@description('Initial runtime database placeholder replaced by the credential workflow before release.')
param bootstrapRuntimeDatabaseUrl string = newGuid()

var isBootstrap = infrastructureMode == 'bootstrap'
var foundryProjectEndpoint = 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${foundryProjectName}'
var foundryHostedResponsesUrl = '${foundryProjectEndpoint}/agents/${hostedAgentName}/endpoint/protocols/openai/responses?api-version=v1'

resource foundryAccountBootstrap 'Microsoft.CognitiveServices/accounts@2025-06-01' = if (isBootstrap) {
  name: foundryAccountName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: foundryCustomSubDomainName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
  tags: tags
}

resource foundryProjectBootstrap 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = if (isBootstrap) {
  parent: foundryAccountBootstrap
  name: foundryProjectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: 'Public Foundry-hosted LangGraph underwriting workflow'
  }
}

resource foundryChatDeploymentBootstrap 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (isBootstrap) {
  parent: foundryAccountBootstrap
  name: foundryChatDeploymentName
  sku: {
    name: foundryChatModelSkuName
    capacity: foundryChatModelCapacity
  }
  properties: {
    model: {
      format: foundryChatModelFormat
      name: foundryChatModelName
      version: foundryChatModelVersion
    }
    raiPolicyName: foundryRaiPolicyName
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

resource foundryEmbeddingsDeploymentBootstrap 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (isBootstrap) {
  parent: foundryAccountBootstrap
  name: foundryEmbeddingsDeploymentName
  dependsOn: [
    foundryChatDeploymentBootstrap
  ]
  sku: {
    name: foundryChatModelSkuName
    capacity: foundryEmbeddingsModelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: foundryEmbeddingsModelVersion
    }
    raiPolicyName: foundryRaiPolicyName
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

resource foundryEvaluationDeploymentBootstrap 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (isBootstrap) {
  parent: foundryAccountBootstrap
  name: foundryEvaluationDeploymentName
  dependsOn: [
    foundryEmbeddingsDeploymentBootstrap
  ]
  sku: {
    name: foundryChatModelSkuName
    capacity: foundryEvaluationModelCapacity
  }
  properties: {
    model: {
      format: foundryChatModelFormat
      name: foundryChatModelName
      version: foundryChatModelVersion
    }
    raiPolicyName: foundryRaiPolicyName
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

resource containerRegistryBootstrap 'Microsoft.ContainerRegistry/registries@2023-07-01' = if (isBootstrap) {
  name: containerRegistryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
  tags: tags
}

resource logAnalyticsWorkspaceBootstrap 'Microsoft.OperationalInsights/workspaces@2023-09-01' = if (isBootstrap) {
  name: logAnalyticsWorkspaceName
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
  tags: tags
}

resource applicationInsightsBootstrap 'Microsoft.Insights/components@2020-02-02' = if (isBootstrap) {
  name: applicationInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspaceBootstrap.id
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
  tags: tags
}

resource publicBackendManagedIdentityBootstrap 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (isBootstrap) {
  name: publicBackendManagedIdentityName
  location: location
  tags: tags
}

resource publicFrontendManagedIdentityBootstrap 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (isBootstrap) {
  name: publicFrontendManagedIdentityName
  location: location
  tags: tags
}

resource containerAppsEnvironmentBootstrap 'Microsoft.App/managedEnvironments@2024-03-01' = if (isBootstrap) {
  name: containerAppsEnvironmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspaceBootstrap!.properties.customerId
        sharedKey: listKeys(logAnalyticsWorkspaceBootstrap!.id, '2023-09-01').primarySharedKey
      }
    }
  }
  tags: tags
}

resource postgresServerBootstrap 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = if (isBootstrap) {
  name: postgresServerName
  location: postgresServerLocation
  sku: {
    name: postgresSkuName
    tier: postgresSkuTier
  }
  properties: {
    administratorLogin: postgresAdministratorLogin
    administratorLoginPassword: postgresAdministratorPassword
    version: postgresVersion
    storage: {
      storageSizeGB: postgresStorageSizeGB
    }
    backup: {
      backupRetentionDays: postgresBackupRetentionDays
      geoRedundantBackup: postgresGeoRedundantBackup
    }
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Enabled'
      tenantId: subscription().tenantId
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
  }
  tags: tags
}

resource postgresAzureServicesFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = if (isBootstrap) {
  parent: postgresServerBootstrap
  name: 'allow-all-temporary'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource postgresReleaseOperatorFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = if (isBootstrap) {
  parent: postgresServerBootstrap
  name: 'allow-release-operator'
  properties: {
    startIpAddress: postgresOperatorIp
    endIpAddress: postgresOperatorIp
  }
}

resource postgresRuntimeDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = if (isBootstrap) {
  parent: postgresServerBootstrap
  name: postgresDatabaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource evaluationStorageAccountBootstrap 'Microsoft.Storage/storageAccounts@2024-01-01' = if (isBootstrap) {
  name: evaluationStorageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
    }
  }
  tags: tags
}

resource acrPullRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
}

resource acrRepositoryReaderRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: 'b93aa761-3e63-49ed-ac28-beffa264f7ac'
}

resource logAnalyticsReaderRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '73c42c96-874c-492b-b04d-ab87d138a893'
}

resource cognitiveServicesOpenAIUserRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
}

resource foundryUserRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
}

resource storageBlobDataOwnerRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
}

resource containerRegistryRoleScope 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: containerRegistryName
}

resource foundryAccountRoleScope 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource foundryProjectRoleScope 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: foundryAccountRoleScope
  name: foundryProjectName
}

resource applicationInsightsRoleScope 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}

resource logAnalyticsWorkspaceRoleScope 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource evaluationStorageAccountRoleScope 'Microsoft.Storage/storageAccounts@2024-01-01' existing = {
  name: evaluationStorageAccountName
}

resource backendAcrPullBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid('resource-scope-v2', containerRegistryRoleScope.id, publicBackendManagedIdentityBootstrap!.id, acrPullRole.id)
  scope: containerRegistryRoleScope
  properties: {
    roleDefinitionId: acrPullRole.id
    principalId: publicBackendManagedIdentityBootstrap!.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource frontendAcrPullBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid('resource-scope-v2', containerRegistryRoleScope.id, publicFrontendManagedIdentityBootstrap!.id, acrPullRole.id)
  scope: containerRegistryRoleScope
  properties: {
    roleDefinitionId: acrPullRole.id
    principalId: publicFrontendManagedIdentityBootstrap!.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource foundryProjectAcrPullBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid('resource-scope-v2', containerRegistryRoleScope.id, foundryProjectBootstrap!.id, acrPullRole.id)
  scope: containerRegistryRoleScope
  properties: {
    roleDefinitionId: acrPullRole.id
    principalId: foundryProjectBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource foundryProjectAcrRepositoryReaderBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid('resource-scope-v2', containerRegistryRoleScope.id, foundryProjectBootstrap!.id, acrRepositoryReaderRole.id)
  scope: containerRegistryRoleScope
  properties: {
    roleDefinitionId: acrRepositoryReaderRole.id
    principalId: foundryProjectBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource foundryProjectApplicationInsightsReaderBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid(applicationInsightsRoleScope.id, foundryProjectBootstrap!.id, logAnalyticsReaderRole.id)
  scope: applicationInsightsRoleScope
  properties: {
    roleDefinitionId: logAnalyticsReaderRole.id
    principalId: foundryProjectBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource foundryProjectLogAnalyticsReaderBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid('resource-scope-v2', logAnalyticsWorkspaceRoleScope.id, foundryProjectBootstrap!.id, logAnalyticsReaderRole.id)
  scope: logAnalyticsWorkspaceRoleScope
  properties: {
    roleDefinitionId: logAnalyticsReaderRole.id
    principalId: foundryProjectBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource foundryProjectOpenAIUserBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid('resource-scope-v2', foundryAccountRoleScope.id, foundryProjectBootstrap!.id, cognitiveServicesOpenAIUserRole.id)
  scope: foundryAccountRoleScope
  properties: {
    roleDefinitionId: cognitiveServicesOpenAIUserRole.id
    principalId: foundryProjectBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource publicBackendFoundryUserBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid('resource-scope-v2', foundryProjectRoleScope.id, publicBackendManagedIdentityBootstrap!.id, foundryUserRole.id)
  scope: foundryProjectRoleScope
  properties: {
    roleDefinitionId: foundryUserRole.id
    principalId: publicBackendManagedIdentityBootstrap!.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource foundryAccountEvaluationStorageAccessBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid('resource-scope-v2', evaluationStorageAccountRoleScope.id, foundryAccountBootstrap!.id, storageBlobDataOwnerRole.id)
  scope: evaluationStorageAccountRoleScope
  properties: {
    roleDefinitionId: storageBlobDataOwnerRole.id
    principalId: foundryAccountBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource foundryProjectEvaluationStorageAccessBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid('resource-scope-v2', evaluationStorageAccountRoleScope.id, foundryProjectBootstrap!.id, storageBlobDataOwnerRole.id)
  scope: evaluationStorageAccountRoleScope
  properties: {
    roleDefinitionId: storageBlobDataOwnerRole.id
    principalId: foundryProjectBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource projectApplicationInsightsConnectionBootstrap 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = if (isBootstrap) {
  parent: foundryProjectBootstrap
  name: 'ApplicationInsights'
  properties: {
    category: 'AppInsights'
    target: applicationInsightsBootstrap!.id
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: applicationInsightsBootstrap!.properties.ConnectionString
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: applicationInsightsBootstrap!.id
    }
  }
  dependsOn: [
    foundryProjectApplicationInsightsReaderBootstrap
    foundryProjectLogAnalyticsReaderBootstrap
  ]
}

resource evaluationStorageConnectionBootstrap 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = if (isBootstrap) {
  parent: foundryAccountBootstrap
  name: 'evaluation-artifacts'
  properties: {
    category: 'AzureStorageAccount'
    target: evaluationStorageAccountBootstrap!.properties.primaryEndpoints.blob
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: evaluationStorageAccountBootstrap!.id
      location: evaluationStorageAccountBootstrap!.location
      purpose: 'foundry-evaluation-artifacts'
    }
  }
  dependsOn: [
    foundryAccountEvaluationStorageAccessBootstrap
    foundryProjectEvaluationStorageAccessBootstrap
  ]
}

resource runtimeStorageConnectionBootstrap 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = if (isBootstrap) {
  parent: foundryAccountBootstrap
  name: 'runtime-storage'
  properties: {
    category: 'AzureStorageAccount'
    target: evaluationStorageAccountBootstrap!.properties.primaryEndpoints.blob
    authType: 'AAD'
    isSharedToAll: false
    metadata: {
      ApiType: 'Azure'
      ResourceId: evaluationStorageAccountBootstrap!.id
      location: evaluationStorageAccountBootstrap!.location
      purpose: 'foundry-runtime-artifacts'
    }
  }
  dependsOn: [
    foundryAccountEvaluationStorageAccessBootstrap
    foundryProjectEvaluationStorageAccessBootstrap
  ]
}

resource backendContainerAppBootstrap 'Microsoft.App/containerApps@2024-03-01' = if (isBootstrap) {
  name: backendContainerAppName
  location: location
  tags: union(tags, {
    'azd-service-name': 'backend'
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${publicBackendManagedIdentityBootstrap!.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironmentBootstrap!.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false
        allowInsecure: false
        targetPort: 80
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistryBootstrap!.properties.loginServer
          identity: publicBackendManagedIdentityBootstrap!.id
        }
      ]
      secrets: [
        {
          name: 'runtime-db-url'
          value: bootstrapRuntimeDatabaseUrl
        }
        {
          name: 'appinsights-connection-string'
          value: applicationInsightsBootstrap!.properties.ConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: bootstrapBackendImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'DATABASE_URL'
              secretRef: 'runtime-db-url'
            }
            {
              name: 'RUNTIME_DATABASE_URL'
              secretRef: 'runtime-db-url'
            }
            {
              name: 'DB_AUTH_MODE'
              value: 'password'
            }
            {
              name: 'DB_SCHEMA_MANAGED_EXTERNALLY'
              value: 'true'
            }
            {
              name: 'DB_SSLMODE'
              value: 'require'
            }
            {
              name: 'UNDERWRITING_EXECUTION_MODE'
              value: 'hosted'
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'appinsights-connection-string'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
}

resource frontendContainerAppBootstrap 'Microsoft.App/containerApps@2024-03-01' = if (isBootstrap) {
  name: frontendContainerAppName
  location: location
  tags: union(tags, {
    'azd-service-name': 'frontend'
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${publicFrontendManagedIdentityBootstrap!.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironmentBootstrap!.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 80
        transport: 'auto'
      }
      registries: [
        {
          server: containerRegistryBootstrap!.properties.loginServer
          identity: publicFrontendManagedIdentityBootstrap!.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: bootstrapFrontendImage
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'NGINX_API_UPSTREAM'
              value: 'https://${backendContainerAppBootstrap!.properties.configuration.ingress.fqdn}'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
}

var foundryAccountId = resourceId('Microsoft.CognitiveServices/accounts', foundryAccountName)
var foundryProjectId = resourceId('Microsoft.CognitiveServices/accounts/projects', foundryAccountName, foundryProjectName)
var containerRegistryId = resourceId('Microsoft.ContainerRegistry/registries', containerRegistryName)
var applicationInsightsId = resourceId('Microsoft.Insights/components', applicationInsightsName)
var logAnalyticsWorkspaceId = resourceId('Microsoft.OperationalInsights/workspaces', logAnalyticsWorkspaceName)
var containerAppsEnvironmentId = resourceId('Microsoft.App/managedEnvironments', containerAppsEnvironmentName)
var backendContainerAppId = resourceId('Microsoft.App/containerApps', backendContainerAppName)
var frontendContainerAppId = resourceId('Microsoft.App/containerApps', frontendContainerAppName)
var postgresServerId = resourceId('Microsoft.DBforPostgreSQL/flexibleServers', postgresServerName)

output AZURE_AI_PROJECT_ENDPOINT string = foundryProjectEndpoint
output AZURE_AI_PROJECT_ID string = foundryProjectId
output FOUNDRY_PROJECT_ENDPOINT string = foundryProjectEndpoint
output FOUNDRY_PROJECTS_ENDPOINT string = foundryProjectEndpoint
output FOUNDRY_ACCOUNT_NAME string = foundryAccountName
output FOUNDRY_PROJECT_NAME string = foundryProjectName
output FOUNDRY_HOSTED_RESPONSES_URL string = foundryHostedResponsesUrl
output FOUNDRY_RESPONSES_ENDPOINT string = foundryHostedResponsesUrl
output FOUNDRY_MODEL_DEPLOYMENT_NAME string = foundryChatDeploymentName
output FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME string = foundryEmbeddingsDeploymentName
output FOUNDRY_EVAL_MODEL string = foundryEvaluationDeploymentName
output HOSTED_AGENT_NAME string = hostedAgentName
output FOUNDRY_RUNTIME_CONNECTION_NAME string = foundryRuntimeConnectionName
output AZURE_OPENAI_ENDPOINT string = reference(foundryAccountId, '2025-06-01').endpoint
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistryName
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = reference(containerRegistryId, '2023-07-01').loginServer
output APPLICATIONINSIGHTS_RESOURCE_ID string = applicationInsightsId
output APPLICATIONINSIGHTS_CONNECTION_STRING string = reference(applicationInsightsId, '2020-02-02').ConnectionString
output LOG_ANALYTICS_WORKSPACE_ID string = logAnalyticsWorkspaceId
output AZURE_POSTGRES_SERVER_FQDN string = reference(postgresServerId, '2023-06-01-preview').fullyQualifiedDomainName
output POSTGRES_SERVER_NAME string = postgresServerName
output POSTGRES_SERVER_LOCATION string = postgresServerLocation
output POSTGRES_DATABASE string = postgresDatabaseName
output AZURE_CONTAINER_APPS_ENVIRONMENT_ID string = containerAppsEnvironmentId
output CONTAINER_APPS_ENVIRONMENT_NAME string = containerAppsEnvironmentName
output BACKEND_CONTAINER_APP_ID string = backendContainerAppId
output BACKEND_CONTAINER_APP_NAME string = backendContainerAppName
output FRONTEND_CONTAINER_APP_ID string = frontendContainerAppId
output FRONTEND_CONTAINER_APP_NAME string = frontendContainerAppName
output SERVICE_BACKEND_RESOURCE_NAME string = backendContainerAppName
output SERVICE_FRONTEND_RESOURCE_NAME string = frontendContainerAppName
output SERVICE_UNDERWRITING_HOSTED_RESOURCE_NAME string = hostedAgentName
output DB_SCHEMA_MANAGED_EXTERNALLY string = 'true'
output PUBLIC_BACKEND_MANAGED_IDENTITY_NAME string = publicBackendManagedIdentityName
output PUBLIC_FRONTEND_MANAGED_IDENTITY_NAME string = publicFrontendManagedIdentityName
output BACKEND_IMAGE_REPOSITORY string = backendImageRepository
output FRONTEND_IMAGE_REPOSITORY string = frontendImageRepository
output API_BASE_URL string = 'https://${reference(backendContainerAppId, '2024-03-01').configuration.ingress.fqdn}'
output WEB_URL string = 'https://${reference(frontendContainerAppId, '2024-03-01').configuration.ingress.fqdn}'
