targetScope = 'resourceGroup'

@allowed([
  'bootstrap'
  'reuse'
])
@description('bootstrap creates the private lane. reuse resolves existing private-lane names without mutating resources or role assignments.')
param infrastructureMode string = 'bootstrap'

@description('Deploy resources that require the Foundry account and account capability host to be fully Succeeded.')
param deployFoundryReadyResources bool = false

@minLength(3)
@maxLength(15)
@description('Lowercase alphanumeric prefix used to derive private-lane resource names.')
param namePrefix string

@allowed([
  'eastus2'
])
@description('Private lane location.')
param location string = 'eastus2'

@description('Tags applied to private-lane resources.')
param tags object = {}

@description('Name of the isolated customer-owned virtual network.')
param privateVnetName string = 'order-resolution-private-vnet'

@description('Name of the Foundry Agent Service delegated subnet.')
param foundryAgentSubnetName string = 'foundry-agents'

@description('Name of the Container Apps infrastructure subnet.')
param containerAppsSubnetName string = 'container-apps-infra'

@description('Name of the private endpoint subnet.')
param privateEndpointSubnetName string = 'private-endpoints'

@description('Name of the no-public-IP release runner subnet.')
param privateRunnerSubnetName string = 'private-runner'

@description('Foundry account name.')
param foundryAccountName string = take('${toLower(namePrefix)}${uniqueString(subscription().id, resourceGroup().id, namePrefix)}ai', 64)

@description('Foundry project name.')
param foundryProjectName string = 'order-resolution-private'

@description('Foundry custom subdomain.')
param foundryCustomSubDomainName string = foundryAccountName

@description('Hosted agent name used to compose the Responses endpoint.')
param hostedAgentName string = 'order-resolution-hosted'

@description('Foundry chat deployment name.')
param foundryChatDeploymentName string = 'order-resolution-private-gpt-4-1-mini'

@description('Foundry chat model format.')
param foundryChatModelFormat string = 'OpenAI'

@description('Foundry chat model name.')
param foundryChatModelName string = 'gpt-4.1-mini'

@description('Foundry chat model version.')
param foundryChatModelVersion string = '2025-04-14'

@description('Foundry chat deployment SKU.')
@allowed([
  'Standard'
  'DataZoneStandard'
  'GlobalStandard'
])
param foundryChatModelSkuName string = 'Standard'

@minValue(1)
@description('Foundry chat deployment capacity in thousands of TPM.')
param foundryChatModelCapacity int = 50

@description('Foundry embeddings deployment name.')
param foundryEmbeddingsDeploymentName string = 'order-resolution-private-text-embedding-3-small'

@description('Foundry embeddings model version.')
param foundryEmbeddingsModelVersion string = '1'

@minValue(1)
@description('Foundry embeddings deployment capacity in thousands of TPM.')
param foundryEmbeddingsModelCapacity int = 10

@description('Foundry evaluator deployment name.')
param foundryEvaluationDeploymentName string = 'order-resolution-private-gpt-4-1-mini-evaluation'

@minValue(1)
@description('Foundry evaluator deployment capacity in thousands of TPM.')
param foundryEvaluationModelCapacity int = 50

@description('Responsible AI policy used by Foundry model deployments.')
param foundryRaiPolicyName string = 'Microsoft.Default'

@description('Private Premium Azure Container Registry name.')
param containerRegistryName string = take('${toLower(namePrefix)}${uniqueString(subscription().id, resourceGroup().id, namePrefix)}acr', 50)

@description('Private standard-agent storage account name.')
param standardAgentStorageAccountName string = take('${toLower(namePrefix)}${uniqueString(subscription().id, resourceGroup().id, namePrefix)}st', 24)

@description('Private standard-agent Cosmos DB account name.')
param standardAgentCosmosAccountName string = take('${toLower(namePrefix)}${uniqueString(subscription().id, resourceGroup().id, namePrefix)}cosmos', 44)

@description('Private standard-agent Azure AI Search service name.')
param standardAgentSearchName string = take('${toLower(namePrefix)}${uniqueString(subscription().id, resourceGroup().id, namePrefix)}search', 60)

@description('Azure AI Search region; East US 2 currently blocks creation of new Search services.')
param standardAgentSearchLocation string = 'westus3'

@description('Log Analytics workspace name.')
param logAnalyticsWorkspaceName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-log', 63)

@description('Application Insights component name.')
param applicationInsightsName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-appi', 64)

@description('Azure Monitor Private Link Scope name.')
param azureMonitorPrivateLinkScopeName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-ampls', 80)

@description('VNet-integrated Container Apps environment name.')
param containerAppsEnvironmentName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-cae', 32)

@description('Internal FastAPI wrapper Container App name.')
param backendContainerAppName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-backend', 32)

@description('External frontend Container App name.')
param frontendContainerAppName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-frontend', 32)

@description('User-assigned identity attached to the internal wrapper Container App.')
param privateBackendManagedIdentityName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-backend-mi', 128)

@description('User-assigned identity attached to the external frontend Container App.')
param privateFrontendManagedIdentityName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-frontend-mi', 128)

@description('ACR repository written by immutable internal-wrapper releases.')
param backendImageRepository string = 'order-resolution-private-backend'

@description('ACR repository written by immutable frontend releases.')
param frontendImageRepository string = 'order-resolution-private-frontend'

@description('Temporary image used only until the first immutable backend release.')
param bootstrapBackendImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Temporary image used only until the first immutable frontend release.')
param bootstrapFrontendImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Private PostgreSQL Flexible Server name.')
param postgresServerName string = take('${toLower(namePrefix)}${uniqueString(subscription().id, resourceGroup().id, namePrefix)}pg', 63)

@secure()
@description('PostgreSQL administrator password required only during bootstrap.')
param postgresAdministratorPassword string

@description('PostgreSQL administrator login.')
param postgresAdministratorLogin string = 'pgadmin'

@description('Database used by the order-resolution runtime.')
param postgresDatabaseName string = 'order_resolution'

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

@description('Private runner virtual machine name.')
param privateRunnerVmName string = take('${namePrefix}-${uniqueString(subscription().id, resourceGroup().id, namePrefix)}-runner', 64)

@description('Private runner administrator username.')
param privateRunnerAdminUsername string = 'runcommand'

@description('SSH public key for the private runner. Required only for bootstrap and never stored in deployment profiles.')
param privateRunnerSshPublicKey string = ''

@secure()
@description('Initial runtime database placeholder replaced by the private-runner credential workflow before release.')
param bootstrapRuntimeDatabaseUrl string = newGuid()

var isBootstrap = infrastructureMode == 'bootstrap'
var isFoundryConvergencePhase = isBootstrap && !deployFoundryReadyResources
var isFoundryReadyPhase = isBootstrap && deployFoundryReadyResources
var foundryProjectEndpoint = 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${foundryProjectName}'
var foundryHostedResponsesUrl = '${foundryProjectEndpoint}/agents/${hostedAgentName}/endpoint/protocols/openai/responses?api-version=v1'
var privateVnetAddressSpace = '10.74.0.0/16'
var searchPrivateVnetAddressSpace = '10.75.0.0/24'
var foundryAgentSubnetPrefix = '10.74.0.0/24'
var containerAppsSubnetPrefix = '10.74.2.0/23'
var privateEndpointSubnetPrefix = '10.74.4.0/24'
var privateRunnerSubnetPrefix = '10.74.5.0/27'
var searchPrivateEndpointSubnetPrefix = '10.75.0.0/27'
var searchPrivateVnetName = '${privateVnetName}-search'
var searchPrivateEndpointSubnetName = 'private-endpoints'
var projectCapabilityHostName = 'order-resolution-private-agent-host'
var accountCapabilityHostName = '${foundryAccountName}@aml_aiagentservice'
var privateDnsZoneNames = [
  'privatelink.services.ai.azure.com'
  'privatelink.openai.azure.com'
  'privatelink.cognitiveservices.azure.com'
  'privatelink.search.windows.net'
  'privatelink.blob.${environment().suffixes.storage}'
  'privatelink.documents.azure.com'
  'privatelink.azurecr.io'
  'privatelink.postgres.database.azure.com'
  'privatelink.monitor.azure.com'
  'privatelink.oms.opinsights.azure.com'
  'privatelink.ods.opinsights.azure.com'
  'privatelink.agentsvc.azure-automation.net'
]
var foundryProjectId = resourceId('Microsoft.CognitiveServices/accounts/projects', foundryAccountName, foundryProjectName)
var applicationInsightsId = resourceId('Microsoft.Insights/components', applicationInsightsName)
var logAnalyticsWorkspaceId = resourceId('Microsoft.OperationalInsights/workspaces', logAnalyticsWorkspaceName)
var containerAppsEnvironmentId = resourceId('Microsoft.App/managedEnvironments', containerAppsEnvironmentName)
var backendContainerAppId = resourceId('Microsoft.App/containerApps', backendContainerAppName)
var frontendContainerAppId = resourceId('Microsoft.App/containerApps', frontendContainerAppName)

resource privateVnetBootstrap 'Microsoft.Network/virtualNetworks@2024-05-01' = if (isBootstrap) {
  name: privateVnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        privateVnetAddressSpace
      ]
    }
  }
  tags: tags
}

resource searchPrivateVnetBootstrap 'Microsoft.Network/virtualNetworks@2024-05-01' = if (isBootstrap) {
  name: searchPrivateVnetName
  location: standardAgentSearchLocation
  properties: {
    addressSpace: {
      addressPrefixes: [
        searchPrivateVnetAddressSpace
      ]
    }
  }
  tags: tags
}

resource foundryAgentSubnetBootstrap 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = if (isBootstrap) {
  parent: privateVnetBootstrap
  name: foundryAgentSubnetName
  properties: {
    addressPrefix: foundryAgentSubnetPrefix
    delegations: [
      {
        name: 'foundry-agent-environments'
        properties: {
          serviceName: 'Microsoft.App/environments'
        }
      }
    ]
  }
}

resource containerAppsSubnetBootstrap 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = if (isBootstrap) {
  parent: privateVnetBootstrap
  name: containerAppsSubnetName
  properties: {
    addressPrefix: containerAppsSubnetPrefix
    delegations: [
      {
        name: 'container-apps-environments'
        properties: {
          serviceName: 'Microsoft.App/environments'
        }
      }
    ]
  }
}

resource privateEndpointSubnetBootstrap 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = if (isBootstrap) {
  parent: privateVnetBootstrap
  name: privateEndpointSubnetName
  properties: {
    addressPrefix: privateEndpointSubnetPrefix
    privateEndpointNetworkPolicies: 'Disabled'
  }
}

resource searchPrivateEndpointSubnetBootstrap 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = if (isBootstrap) {
  parent: searchPrivateVnetBootstrap
  name: searchPrivateEndpointSubnetName
  properties: {
    addressPrefix: searchPrivateEndpointSubnetPrefix
    privateEndpointNetworkPolicies: 'Disabled'
  }
}

resource privateToSearchVnetPeeringBootstrap 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings@2024-05-01' = if (isBootstrap) {
  parent: privateVnetBootstrap
  name: 'to-search-private-vnet'
  properties: {
    allowVirtualNetworkAccess: true
    allowForwardedTraffic: true
    allowGatewayTransit: false
    useRemoteGateways: false
    remoteVirtualNetwork: {
      id: searchPrivateVnetBootstrap!.id
    }
  }
  dependsOn: [
    foundryAgentSubnetBootstrap
    containerAppsSubnetBootstrap
    privateEndpointSubnetBootstrap
    privateRunnerSubnetBootstrap
    searchPrivateEndpointSubnetBootstrap
  ]
}

resource searchToPrivateVnetPeeringBootstrap 'Microsoft.Network/virtualNetworks/virtualNetworkPeerings@2024-05-01' = if (isBootstrap) {
  parent: searchPrivateVnetBootstrap
  name: 'to-primary-private-vnet'
  properties: {
    allowVirtualNetworkAccess: true
    allowForwardedTraffic: true
    allowGatewayTransit: false
    useRemoteGateways: false
    remoteVirtualNetwork: {
      id: privateVnetBootstrap!.id
    }
  }
  dependsOn: [
    foundryAgentSubnetBootstrap
    containerAppsSubnetBootstrap
    privateEndpointSubnetBootstrap
    privateRunnerSubnetBootstrap
    searchPrivateEndpointSubnetBootstrap
  ]
}

resource privateRunnerNsgBootstrap 'Microsoft.Network/networkSecurityGroups@2024-05-01' = if (isBootstrap) {
  name: take('${privateRunnerVmName}-nsg', 80)
  location: location
  properties: {
    securityRules: [
      {
        name: 'allow-azure-cloud-https'
        properties: {
          access: 'Allow'
          direction: 'Outbound'
          priority: 100
          protocol: 'Tcp'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: 'AzureCloud'
          destinationPortRange: '443'
        }
      }
      {
        name: 'allow-package-egress'
        properties: {
          access: 'Allow'
          direction: 'Outbound'
          priority: 120
          protocol: 'Tcp'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: 'Internet'
          destinationPortRanges: [
            '80'
            '443'
          ]
        }
      }
      {
        name: 'deny-internet-outbound'
        properties: {
          access: 'Deny'
          direction: 'Outbound'
          priority: 400
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: 'Internet'
          destinationPortRange: '*'
        }
      }
    ]
  }
  tags: tags
}

resource privateRunnerNatPublicIpBootstrap 'Microsoft.Network/publicIPAddresses@2024-05-01' = if (isBootstrap) {
  name: take('${privateRunnerVmName}-nat-pip', 80)
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
    publicIPAddressVersion: 'IPv4'
  }
  tags: union(tags, {
    purpose: 'runner-egress-only'
  })
}

resource privateRunnerNatGatewayBootstrap 'Microsoft.Network/natGateways@2024-05-01' = if (isBootstrap) {
  name: take('${privateRunnerVmName}-nat', 80)
  location: location
  sku: {
    name: 'Standard'
  }
  properties: {
    idleTimeoutInMinutes: 10
    publicIpAddresses: [
      {
        id: privateRunnerNatPublicIpBootstrap!.id
      }
    ]
  }
  tags: tags
}

resource privateRunnerSubnetBootstrap 'Microsoft.Network/virtualNetworks/subnets@2024-05-01' = if (isBootstrap) {
  parent: privateVnetBootstrap
  name: privateRunnerSubnetName
  properties: {
    addressPrefix: privateRunnerSubnetPrefix
    networkSecurityGroup: {
      id: privateRunnerNsgBootstrap!.id
    }
    natGateway: {
      id: privateRunnerNatGatewayBootstrap!.id
    }
  }
}

resource privateDnsZoneResourcesBootstrap 'Microsoft.Network/privateDnsZones@2020-06-01' = [for zoneName in privateDnsZoneNames: if (isBootstrap) {
  name: zoneName
  location: 'global'
  tags: tags
}]

resource privateDnsZoneVnetLinksBootstrap 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (zoneName, index) in privateDnsZoneNames: if (isBootstrap) {
  parent: privateDnsZoneResourcesBootstrap[index]
  name: take('${replace(zoneName, '.', '-')}-private-link', 80)
  location: 'global'
  properties: {
    virtualNetwork: {
      id: privateVnetBootstrap!.id
    }
    registrationEnabled: false
  }
}]

resource searchPrivateDnsZoneVnetLinkBootstrap 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = if (isBootstrap) {
  parent: privateDnsZoneResourcesBootstrap[3]
  name: 'search-private-vnet-link'
  location: 'global'
  properties: {
    virtualNetwork: {
      id: searchPrivateVnetBootstrap!.id
    }
    registrationEnabled: false
  }
}

resource foundryAccountBootstrap 'Microsoft.CognitiveServices/accounts@2025-06-01' = if (isFoundryConvergencePhase) {
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
    disableLocalAuth: true
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
      ipRules: []
      virtualNetworkRules: []
    }
    networkInjections: [
      {
        scenario: 'agent'
        subnetArmId: foundryAgentSubnetBootstrap!.id
        useMicrosoftManagedNetwork: false
      }
    ]
  }
  tags: tags
}

resource foundryChatDeploymentBootstrap 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (isFoundryConvergencePhase) {
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

resource foundryEmbeddingsDeploymentBootstrap 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (isFoundryConvergencePhase) {
  parent: foundryAccountBootstrap
  name: foundryEmbeddingsDeploymentName
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
  dependsOn: [
    foundryChatDeploymentBootstrap
  ]
}

resource foundryEvaluationDeploymentBootstrap 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (isFoundryConvergencePhase) {
  parent: foundryAccountBootstrap
  name: foundryEvaluationDeploymentName
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
  dependsOn: [
    foundryEmbeddingsDeploymentBootstrap
  ]
}

resource standardAgentStorageBootstrap 'Microsoft.Storage/storageAccounts@2024-01-01' = if (isBootstrap) {
  name: standardAgentStorageAccountName
  location: location
  sku: {
    name: 'Standard_ZRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      bypass: 'None'
      defaultAction: 'Deny'
      ipRules: []
      virtualNetworkRules: []
    }
  }
  tags: tags
}

resource standardAgentCosmosBootstrap 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' = if (isBootstrap) {
  name: standardAgentCosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    disableLocalAuth: true
    enableAutomaticFailover: false
    enableFreeTier: false
    enableMultipleWriteLocations: false
    publicNetworkAccess: 'Disabled'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
  }
  tags: tags
}

resource standardAgentSearchBootstrap 'Microsoft.Search/searchServices@2024-06-01-preview' = if (isBootstrap) {
  name: standardAgentSearchName
  location: standardAgentSearchLocation
  sku: {
    name: 'standard'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    disableLocalAuth: true
    hostingMode: 'default'
    partitionCount: 1
    publicNetworkAccess: 'disabled'
    replicaCount: 1
    semanticSearch: 'disabled'
    networkRuleSet: {
      bypass: 'None'
      ipRules: []
    }
  }
  tags: tags
}

resource containerRegistryBootstrap 'Microsoft.ContainerRegistry/registries@2025-04-01' = if (isBootstrap) {
  name: containerRegistryName
  location: location
  sku: {
    name: 'Premium'
  }
  properties: {
    adminUserEnabled: false
    networkRuleBypassOptions: 'AzureServices'
    networkRuleSet: {
      defaultAction: 'Deny'
      ipRules: []
    }
    policies: {
      azureADAuthenticationAsArmPolicy: {
        status: 'enabled'
      }
    }
    publicNetworkAccess: 'Disabled'
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
    publicNetworkAccessForIngestion: 'Disabled'
    publicNetworkAccessForQuery: 'Disabled'
  }
  tags: tags
}

resource applicationInsightsBootstrap 'Microsoft.Insights/components@2020-02-02' = if (isBootstrap) {
  name: applicationInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspaceBootstrap!.id
    publicNetworkAccessForIngestion: 'Disabled'
    publicNetworkAccessForQuery: 'Disabled'
  }
  tags: tags
}

resource azureMonitorPrivateLinkScopeBootstrap 'Microsoft.Insights/privateLinkScopes@2021-07-01-preview' = if (isBootstrap) {
  name: azureMonitorPrivateLinkScopeName
  location: 'global'
  properties: {
    accessModeSettings: {
      ingestionAccessMode: 'PrivateOnly'
      queryAccessMode: 'PrivateOnly'
    }
  }
  tags: tags
}

resource azureMonitorApplicationInsightsScopeBootstrap 'Microsoft.Insights/privateLinkScopes/scopedResources@2021-07-01-preview' = if (isBootstrap) {
  parent: azureMonitorPrivateLinkScopeBootstrap
  name: 'application-insights'
  properties: {
    linkedResourceId: applicationInsightsBootstrap!.id
  }
}

resource azureMonitorLogAnalyticsScopeBootstrap 'Microsoft.Insights/privateLinkScopes/scopedResources@2021-07-01-preview' = if (isBootstrap) {
  parent: azureMonitorPrivateLinkScopeBootstrap
  name: 'log-analytics'
  properties: {
    linkedResourceId: logAnalyticsWorkspaceBootstrap!.id
  }
}

resource postgresServerBootstrap 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = if (isBootstrap) {
  name: postgresServerName
  location: location
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
      publicNetworkAccess: 'Disabled'
    }
  }
  tags: tags
}

resource postgresRuntimeDatabaseBootstrap 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = if (isBootstrap) {
  parent: postgresServerBootstrap
  name: postgresDatabaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource privateBackendManagedIdentityBootstrap 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (isBootstrap) {
  name: privateBackendManagedIdentityName
  location: location
  tags: tags
}

resource privateFrontendManagedIdentityBootstrap 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (isBootstrap) {
  name: privateFrontendManagedIdentityName
  location: location
  tags: tags
}

resource privateRunnerNicBootstrap 'Microsoft.Network/networkInterfaces@2024-05-01' = if (isBootstrap) {
  name: take('${privateRunnerVmName}-nic', 80)
  location: location
  properties: {
    enableAcceleratedNetworking: false
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          subnet: {
            id: privateRunnerSubnetBootstrap!.id
          }
        }
      }
    ]
  }
  tags: tags
}

resource privateRunnerVmBootstrap 'Microsoft.Compute/virtualMachines@2024-11-01' = if (isBootstrap) {
  name: privateRunnerVmName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    hardwareProfile: {
      vmSize: 'Standard_D2as_v7'
    }
    osProfile: {
      computerName: privateRunnerVmName
      adminUsername: privateRunnerAdminUsername
      linuxConfiguration: {
        disablePasswordAuthentication: true
        provisionVMAgent: true
        ssh: {
          publicKeys: [
            {
              path: '/home/${privateRunnerAdminUsername}/.ssh/authorized_keys'
              keyData: privateRunnerSshPublicKey
            }
          ]
        }
      }
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'ubuntu-24_04-lts'
        sku: 'server'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: 'StandardSSD_LRS'
        }
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: privateRunnerNicBootstrap!.id
          properties: {
            primary: true
          }
        }
      ]
    }
    diagnosticsProfile: {
      bootDiagnostics: {
        enabled: true
      }
    }
  }
  tags: union(tags, {
    access: 'azure-run-command-only'
  })
}

resource foundryPrivateEndpointBootstrap 'Microsoft.Network/privateEndpoints@2024-05-01' = if (isFoundryReadyPhase) {
  name: take('${foundryAccountName}-pe', 80)
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnetBootstrap!.id
    }
    privateLinkServiceConnections: [
      {
        name: 'foundry-account'
        properties: {
          privateLinkServiceId: foundryAccountRoleScope.id
          groupIds: [
            'account'
          ]
        }
      }
    ]
  }
  tags: tags
}

resource standardAgentStoragePrivateEndpointBootstrap 'Microsoft.Network/privateEndpoints@2024-05-01' = if (isBootstrap) {
  name: take('${standardAgentStorageAccountName}-blob-pe', 80)
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnetBootstrap!.id
    }
    privateLinkServiceConnections: [
      {
        name: 'storage-blob'
        properties: {
          privateLinkServiceId: standardAgentStorageBootstrap!.id
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
  tags: tags
}

resource standardAgentCosmosPrivateEndpointBootstrap 'Microsoft.Network/privateEndpoints@2024-05-01' = if (isBootstrap) {
  name: take('${standardAgentCosmosAccountName}-sql-pe', 80)
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnetBootstrap!.id
    }
    privateLinkServiceConnections: [
      {
        name: 'cosmos-sql'
        properties: {
          privateLinkServiceId: standardAgentCosmosBootstrap!.id
          groupIds: [
            'Sql'
          ]
        }
      }
    ]
  }
  tags: tags
}

resource standardAgentSearchPrivateEndpointBootstrap 'Microsoft.Network/privateEndpoints@2024-05-01' = if (isBootstrap) {
  name: take('${standardAgentSearchName}-search-pe', 80)
  location: standardAgentSearchLocation
  properties: {
    subnet: {
      id: searchPrivateEndpointSubnetBootstrap!.id
    }
    privateLinkServiceConnections: [
      {
        name: 'search-service'
        properties: {
          privateLinkServiceId: standardAgentSearchBootstrap!.id
          groupIds: [
            'searchService'
          ]
        }
      }
    ]
  }
  tags: tags
}

resource containerRegistryPrivateEndpointBootstrap 'Microsoft.Network/privateEndpoints@2024-05-01' = if (isBootstrap) {
  name: take('${containerRegistryName}-registry-pe', 80)
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnetBootstrap!.id
    }
    privateLinkServiceConnections: [
      {
        name: 'container-registry'
        properties: {
          privateLinkServiceId: containerRegistryBootstrap!.id
          groupIds: [
            'registry'
          ]
        }
      }
    ]
  }
  tags: tags
}

resource postgresPrivateEndpointBootstrap 'Microsoft.Network/privateEndpoints@2024-05-01' = if (isBootstrap) {
  name: take('${postgresServerName}-postgres-pe', 80)
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnetBootstrap!.id
    }
    privateLinkServiceConnections: [
      {
        name: 'postgresql-server'
        properties: {
          privateLinkServiceId: postgresServerBootstrap!.id
          groupIds: [
            'postgresqlServer'
          ]
        }
      }
    ]
  }
  tags: tags
}

resource azureMonitorPrivateEndpointBootstrap 'Microsoft.Network/privateEndpoints@2024-05-01' = if (isBootstrap) {
  name: take('${azureMonitorPrivateLinkScopeName}-pe', 80)
  location: location
  properties: {
    subnet: {
      id: privateEndpointSubnetBootstrap!.id
    }
    privateLinkServiceConnections: [
      {
        name: 'azure-monitor'
        properties: {
          privateLinkServiceId: azureMonitorPrivateLinkScopeBootstrap!.id
          groupIds: [
            'azuremonitor'
          ]
        }
      }
    ]
  }
  tags: tags
  dependsOn: [
    azureMonitorApplicationInsightsScopeBootstrap
    azureMonitorLogAnalyticsScopeBootstrap
  ]
}

resource foundryPrivateDnsZoneGroupBootstrap 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (isFoundryReadyPhase) {
  parent: foundryPrivateEndpointBootstrap
  name: 'foundry-dns'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'services-ai'
        properties: {
          privateDnsZoneId: privateDnsZoneResourcesBootstrap[0].id
        }
      }
      {
        name: 'openai'
        properties: {
          privateDnsZoneId: privateDnsZoneResourcesBootstrap[1].id
        }
      }
      {
        name: 'cognitive-services'
        properties: {
          privateDnsZoneId: privateDnsZoneResourcesBootstrap[2].id
        }
      }
    ]
  }
  dependsOn: [
    privateDnsZoneVnetLinksBootstrap
  ]
}

resource standardAgentSearchPrivateDnsZoneGroupBootstrap 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (isBootstrap) {
  parent: standardAgentSearchPrivateEndpointBootstrap
  name: 'search-dns'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'search'
        properties: {
          privateDnsZoneId: privateDnsZoneResourcesBootstrap[3].id
        }
      }
    ]
  }
  dependsOn: [
    privateDnsZoneVnetLinksBootstrap
    searchPrivateDnsZoneVnetLinkBootstrap
    privateToSearchVnetPeeringBootstrap
    searchToPrivateVnetPeeringBootstrap
  ]
}

resource standardAgentStoragePrivateDnsZoneGroupBootstrap 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (isBootstrap) {
  parent: standardAgentStoragePrivateEndpointBootstrap
  name: 'storage-dns'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'blob'
        properties: {
          privateDnsZoneId: privateDnsZoneResourcesBootstrap[4].id
        }
      }
    ]
  }
  dependsOn: [
    privateDnsZoneVnetLinksBootstrap
  ]
}

resource standardAgentCosmosPrivateDnsZoneGroupBootstrap 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (isBootstrap) {
  parent: standardAgentCosmosPrivateEndpointBootstrap
  name: 'cosmos-dns'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'cosmos'
        properties: {
          privateDnsZoneId: privateDnsZoneResourcesBootstrap[5].id
        }
      }
    ]
  }
  dependsOn: [
    privateDnsZoneVnetLinksBootstrap
  ]
}

resource containerRegistryPrivateDnsZoneGroupBootstrap 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (isBootstrap) {
  parent: containerRegistryPrivateEndpointBootstrap
  name: 'registry-dns'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'registry'
        properties: {
          privateDnsZoneId: privateDnsZoneResourcesBootstrap[6].id
        }
      }
    ]
  }
  dependsOn: [
    privateDnsZoneVnetLinksBootstrap
  ]
}

resource postgresPrivateDnsZoneGroupBootstrap 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (isBootstrap) {
  parent: postgresPrivateEndpointBootstrap
  name: 'postgres-dns'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'postgres'
        properties: {
          privateDnsZoneId: privateDnsZoneResourcesBootstrap[7].id
        }
      }
    ]
  }
  dependsOn: [
    privateDnsZoneVnetLinksBootstrap
  ]
}

resource azureMonitorPrivateDnsZoneGroupBootstrap 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-05-01' = if (isBootstrap) {
  parent: azureMonitorPrivateEndpointBootstrap
  name: 'monitor-dns'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'monitor'
        properties: {
          privateDnsZoneId: privateDnsZoneResourcesBootstrap[8].id
        }
      }
      {
        name: 'oms'
        properties: {
          privateDnsZoneId: privateDnsZoneResourcesBootstrap[9].id
        }
      }
      {
        name: 'ods'
        properties: {
          privateDnsZoneId: privateDnsZoneResourcesBootstrap[10].id
        }
      }
      {
        name: 'automation'
        properties: {
          privateDnsZoneId: privateDnsZoneResourcesBootstrap[11].id
        }
      }
    ]
  }
  dependsOn: [
    privateDnsZoneVnetLinksBootstrap
  ]
}

resource foundryProjectBootstrap 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = if (isFoundryReadyPhase) {
  parent: foundryAccountRoleScope
  name: foundryProjectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: 'Private network-secured Foundry-hosted LangGraph order-resolution workflow'
    displayName: 'Order Resolution Private'
  }
  dependsOn: [
    foundryPrivateDnsZoneGroupBootstrap
    standardAgentSearchPrivateDnsZoneGroupBootstrap
    standardAgentStoragePrivateDnsZoneGroupBootstrap
    standardAgentCosmosPrivateDnsZoneGroupBootstrap
  ]
}

resource projectCosmosConnectionBootstrap 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = if (isFoundryReadyPhase) {
  parent: foundryProjectBootstrap
  name: 'private-cosmos'
  properties: {
    category: 'CosmosDB'
    target: standardAgentCosmosBootstrap!.properties.documentEndpoint
    authType: 'AAD'
    metadata: {
      ApiType: 'Azure'
      ResourceId: standardAgentCosmosBootstrap!.id
      location: location
    }
  }
}

resource projectStorageConnectionBootstrap 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = if (isFoundryReadyPhase) {
  parent: foundryProjectBootstrap
  name: 'private-storage'
  properties: {
    category: 'AzureStorageAccount'
    target: standardAgentStorageBootstrap!.properties.primaryEndpoints.blob
    authType: 'AAD'
    metadata: {
      ApiType: 'Azure'
      ResourceId: standardAgentStorageBootstrap!.id
      location: location
    }
  }
}

resource projectSearchConnectionBootstrap 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = if (isFoundryReadyPhase) {
  parent: foundryProjectBootstrap
  name: 'private-search'
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${standardAgentSearchName}.search.windows.net'
    authType: 'AAD'
    metadata: {
      ApiType: 'Azure'
      ResourceId: standardAgentSearchBootstrap!.id
      location: standardAgentSearchLocation
    }
  }
}

resource accountApplicationInsightsConnectionBootstrap 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = if (isFoundryReadyPhase) {
  parent: foundryAccountRoleScope
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
    azureMonitorPrivateDnsZoneGroupBootstrap
  ]
}

resource acrPullRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
}

resource acrPushRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '8311e382-0749-4cb8-b61a-304f252e45ec'
}

resource acrRepositoryReaderRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: 'b93aa761-3e63-49ed-ac28-beffa264f7ac'
}

resource cognitiveServicesOpenAIUserRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
}

resource foundryUserRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '53ca6127-db72-4b80-b1b0-d745d6d5456d'
}

resource storageAccountContributorRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '17d1049b-9a84-46fb-8f53-869881c3d3ab'
}

resource cosmosDbOperatorRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '230815da-be43-4aae-9cb4-875f7bd000aa'
}

resource searchIndexDataContributorRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
}

resource searchServiceContributorRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
}

resource logAnalyticsReaderRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '73c42c96-874c-492b-b04d-ab87d138a893'
}

resource readerRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: 'acdd72a7-3385-48ef-bd42-f606fba81ae7'
}

resource containerAppsContributorRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '358470bc-b998-42bd-ab17-a7e34c199c0f'
}

resource foundryProjectManagerRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: 'eadc314b-1a2d-4efa-be10-5d325db5065e'
}

resource managedIdentityOperatorRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: 'f1a07417-d97a-45cb-824c-7a7467783830'
}

resource privateRunnerDeploymentExecutorRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' = if (isBootstrap) {
  name: guid(resourceGroup().id, 'order-resolution-private-runner-deployment-executor')
  properties: {
    roleName: 'Order Resolution Private Runner Deployment Executor'
    description: 'Allows the lane runner to create and inspect resource-group deployment records only.'
    type: 'CustomRole'
    permissions: [
      {
        actions: [
          'Microsoft.Resources/deployments/*'
        ]
        notActions: []
        dataActions: []
        notDataActions: []
      }
    ]
    assignableScopes: [
      resourceGroup().id
    ]
  }
}

resource containerRegistryRoleScope 'Microsoft.ContainerRegistry/registries@2025-04-01' existing = {
  name: containerRegistryName
}

resource foundryAccountRoleScope 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource foundryProjectRoleScope 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' existing = {
  parent: foundryAccountRoleScope
  name: foundryProjectName
}

resource standardAgentStorageRoleScope 'Microsoft.Storage/storageAccounts@2024-01-01' existing = {
  name: standardAgentStorageAccountName
}

resource standardAgentCosmosRoleScope 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = {
  name: standardAgentCosmosAccountName
}

resource standardAgentSearchRoleScope 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: standardAgentSearchName
}

resource logAnalyticsWorkspaceRoleScope 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource backendAcrPullBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid(containerRegistryRoleScope.id, privateBackendManagedIdentityName, acrPullRole.id)
  scope: containerRegistryRoleScope
  properties: {
    roleDefinitionId: acrPullRole.id
    principalId: privateBackendManagedIdentityBootstrap!.properties.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    containerRegistryBootstrap
  ]
}

resource frontendAcrPullBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid(containerRegistryRoleScope.id, privateFrontendManagedIdentityName, acrPullRole.id)
  scope: containerRegistryRoleScope
  properties: {
    roleDefinitionId: acrPullRole.id
    principalId: privateFrontendManagedIdentityBootstrap!.properties.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    containerRegistryBootstrap
  ]
}

resource projectAcrPullBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isFoundryReadyPhase) {
  name: guid(containerRegistryRoleScope.id, foundryProjectName, acrPullRole.id)
  scope: containerRegistryRoleScope
  properties: {
    roleDefinitionId: acrPullRole.id
    principalId: foundryProjectBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    containerRegistryBootstrap
  ]
}

resource projectAcrRepositoryReaderBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isFoundryReadyPhase) {
  name: guid(containerRegistryRoleScope.id, foundryProjectName, acrRepositoryReaderRole.id)
  scope: containerRegistryRoleScope
  properties: {
    roleDefinitionId: acrRepositoryReaderRole.id
    principalId: foundryProjectBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    containerRegistryBootstrap
  ]
}

resource privateRunnerAcrPushBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid(containerRegistryRoleScope.id, privateRunnerVmName, acrPushRole.id)
  scope: containerRegistryRoleScope
  properties: {
    roleDefinitionId: acrPushRole.id
    principalId: privateRunnerVmBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    containerRegistryBootstrap
  ]
}

resource privateRunnerReaderBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid(resourceGroup().id, privateRunnerVmName, readerRole.id)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: readerRole.id
    principalId: privateRunnerVmBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource privateRunnerContainerAppsContributorBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid(resourceGroup().id, privateRunnerVmName, containerAppsContributorRole.id)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: containerAppsContributorRole.id
    principalId: privateRunnerVmBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource privateRunnerDeploymentExecutorBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid(resourceGroup().id, privateRunnerVmName, privateRunnerDeploymentExecutorRole.id)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: privateRunnerDeploymentExecutorRole.id
    principalId: privateRunnerVmBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource privateRunnerBackendIdentityOperatorBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid(privateBackendManagedIdentityBootstrap!.id, privateRunnerVmName, managedIdentityOperatorRole.id)
  scope: privateBackendManagedIdentityBootstrap
  properties: {
    roleDefinitionId: managedIdentityOperatorRole.id
    principalId: privateRunnerVmBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource privateRunnerFrontendIdentityOperatorBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid(privateFrontendManagedIdentityBootstrap!.id, privateRunnerVmName, managedIdentityOperatorRole.id)
  scope: privateFrontendManagedIdentityBootstrap
  properties: {
    roleDefinitionId: managedIdentityOperatorRole.id
    principalId: privateRunnerVmBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource privateRunnerFoundryProjectManagerBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isFoundryReadyPhase) {
  name: guid(foundryProjectRoleScope.id, privateRunnerVmName, foundryProjectManagerRole.id)
  scope: foundryProjectRoleScope
  properties: {
    roleDefinitionId: foundryProjectManagerRole.id
    principalId: privateRunnerVmBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    foundryProjectBootstrap
  ]
}

resource privateRunnerLogAnalyticsReaderBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isBootstrap) {
  name: guid(logAnalyticsWorkspaceRoleScope.id, privateRunnerVmName, logAnalyticsReaderRole.id)
  scope: logAnalyticsWorkspaceRoleScope
  properties: {
    roleDefinitionId: logAnalyticsReaderRole.id
    principalId: privateRunnerVmBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    logAnalyticsWorkspaceBootstrap
  ]
}

resource projectOpenAIUserBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isFoundryReadyPhase) {
  name: guid(foundryAccountRoleScope.id, foundryProjectName, cognitiveServicesOpenAIUserRole.id)
  scope: foundryAccountRoleScope
  properties: {
    roleDefinitionId: cognitiveServicesOpenAIUserRole.id
    principalId: foundryProjectBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource backendFoundryUserBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isFoundryReadyPhase) {
  name: guid(foundryProjectRoleScope.id, privateBackendManagedIdentityName, foundryUserRole.id)
  scope: foundryProjectRoleScope
  properties: {
    roleDefinitionId: foundryUserRole.id
    principalId: privateBackendManagedIdentityBootstrap!.properties.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    foundryProjectBootstrap
  ]
}

resource projectStorageAccountContributorBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isFoundryReadyPhase) {
  name: guid(standardAgentStorageRoleScope.id, foundryProjectName, storageAccountContributorRole.id)
  scope: standardAgentStorageRoleScope
  properties: {
    roleDefinitionId: storageAccountContributorRole.id
    principalId: foundryProjectBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    standardAgentStorageBootstrap
  ]
}

resource projectCosmosOperatorBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isFoundryReadyPhase) {
  name: guid(standardAgentCosmosRoleScope.id, foundryProjectName, cosmosDbOperatorRole.id)
  scope: standardAgentCosmosRoleScope
  properties: {
    roleDefinitionId: cosmosDbOperatorRole.id
    principalId: foundryProjectBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    standardAgentCosmosBootstrap
  ]
}

resource projectSearchIndexDataContributorBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isFoundryReadyPhase) {
  name: guid(standardAgentSearchRoleScope.id, foundryProjectName, searchIndexDataContributorRole.id)
  scope: standardAgentSearchRoleScope
  properties: {
    roleDefinitionId: searchIndexDataContributorRole.id
    principalId: foundryProjectBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    standardAgentSearchBootstrap
  ]
}

resource projectSearchServiceContributorBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isFoundryReadyPhase) {
  name: guid(standardAgentSearchRoleScope.id, foundryProjectName, searchServiceContributorRole.id)
  scope: standardAgentSearchRoleScope
  properties: {
    roleDefinitionId: searchServiceContributorRole.id
    principalId: foundryProjectBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    standardAgentSearchBootstrap
  ]
}

resource projectLogAnalyticsReaderBootstrap 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (isFoundryReadyPhase) {
  name: guid(logAnalyticsWorkspaceRoleScope.id, foundryProjectName, logAnalyticsReaderRole.id)
  scope: logAnalyticsWorkspaceRoleScope
  properties: {
    roleDefinitionId: logAnalyticsReaderRole.id
    principalId: foundryProjectBootstrap!.identity.principalId
    principalType: 'ServicePrincipal'
  }
  dependsOn: [
    logAnalyticsWorkspaceBootstrap
  ]
}

// The platform creates this account host from networkInjections. Creating another
// account capability host races the platform and can leave a subnet association behind.
resource projectCapabilityHostBootstrap 'Microsoft.CognitiveServices/accounts/projects/capabilityHosts@2025-06-01' = if (isFoundryReadyPhase) {
  parent: foundryProjectBootstrap
  name: projectCapabilityHostName
  properties: {
    #disable-next-line BCP037
    capabilityHostKind: 'Agents'
    threadStorageConnections: [
      projectCosmosConnectionBootstrap.name
    ]
    storageConnections: [
      projectStorageConnectionBootstrap.name
    ]
    vectorStoreConnections: [
      projectSearchConnectionBootstrap.name
    ]
  }
  dependsOn: [
    projectStorageAccountContributorBootstrap
    projectCosmosOperatorBootstrap
    projectSearchIndexDataContributorBootstrap
    projectSearchServiceContributorBootstrap
  ]
}

#disable-next-line BCP053
var projectWorkspaceId = foundryProjectBootstrap!.properties.internalId
var projectWorkspaceIdGuid = '${substring(projectWorkspaceId, 0, 8)}-${substring(projectWorkspaceId, 8, 4)}-${substring(projectWorkspaceId, 12, 4)}-${substring(projectWorkspaceId, 16, 4)}-${substring(projectWorkspaceId, 20, 12)}'

module standardAgentDataRoleAssignmentsBootstrap 'modules/standard-agent-data-role-assignments.bicep' = if (isFoundryReadyPhase) {
  name: 'standard-agent-data-roles-${uniqueString(resourceGroup().id, foundryProjectName)}'
  params: {
    storageAccountName: standardAgentStorageAccountName
    cosmosAccountName: standardAgentCosmosAccountName
    projectPrincipalId: foundryProjectBootstrap!.identity.principalId
    projectWorkspaceId: projectWorkspaceIdGuid
  }
  dependsOn: [
    projectCapabilityHostBootstrap
  ]
}

resource containerAppsEnvironmentBootstrap 'Microsoft.App/managedEnvironments@2025-01-01' = if (isBootstrap) {
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
    vnetConfiguration: {
      infrastructureSubnetId: containerAppsSubnetBootstrap!.id
      internal: false
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
  tags: tags
}

resource backendContainerAppBootstrap 'Microsoft.App/containerApps@2025-01-01' = if (isBootstrap) {
  name: backendContainerAppName
  location: location
  tags: union(tags, {
    'azd-service-name': 'backend'
    network: 'private'
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${privateBackendManagedIdentityBootstrap!.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironmentBootstrap!.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false
        allowInsecure: false
        targetPort: 8000
        transport: 'auto'
      }
      registries: [
        {
          server: '${containerRegistryName}.azurecr.io'
          identity: privateBackendManagedIdentityBootstrap!.id
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
  dependsOn: [
    backendAcrPullBootstrap
    backendFoundryUserBootstrap
    postgresPrivateDnsZoneGroupBootstrap
    azureMonitorPrivateDnsZoneGroupBootstrap
  ]
}

resource frontendContainerAppBootstrap 'Microsoft.App/containerApps@2025-01-01' = if (isBootstrap) {
  name: frontendContainerAppName
  location: location
  tags: union(tags, {
    'azd-service-name': 'frontend'
    network: 'external-ingress-private-backend'
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${privateFrontendManagedIdentityBootstrap!.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnvironmentBootstrap!.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 5173
        transport: 'auto'
      }
      registries: [
        {
          server: '${containerRegistryName}.azurecr.io'
          identity: privateFrontendManagedIdentityBootstrap!.id
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
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
  dependsOn: [
    frontendAcrPullBootstrap
  ]
}

output AZURE_AI_PROJECT_ENDPOINT string = foundryProjectEndpoint
output AZURE_AI_PROJECT_ID string = foundryProjectId
output FOUNDRY_PROJECT_ENDPOINT string = foundryProjectEndpoint
output FOUNDRY_PROJECTS_ENDPOINT string = foundryProjectEndpoint
output FOUNDRY_ACCOUNT_NAME string = foundryAccountName
output FOUNDRY_PROJECT_NAME string = foundryProjectName
output FOUNDRY_ACCOUNT_CAPABILITY_HOST_NAME string = accountCapabilityHostName
output FOUNDRY_PROJECT_CAPABILITY_HOST_NAME string = projectCapabilityHostName
output FOUNDRY_HOSTED_RESPONSES_URL string = foundryHostedResponsesUrl
output FOUNDRY_MODEL_DEPLOYMENT_NAME string = foundryChatDeploymentName
output FOUNDRY_EMBEDDINGS_DEPLOYMENT_NAME string = foundryEmbeddingsDeploymentName
output FOUNDRY_EVAL_MODEL string = foundryEvaluationDeploymentName
output HOSTED_AGENT_NAME string = hostedAgentName
output AZURE_OPENAI_ENDPOINT string = 'https://${foundryAccountName}.openai.azure.com/'
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistryName
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = '${containerRegistryName}.azurecr.io'
output APPLICATIONINSIGHTS_RESOURCE_ID string = applicationInsightsId
output APPLICATIONINSIGHTS_CONNECTION_STRING string = reference(applicationInsightsId, '2020-02-02').ConnectionString
output APPLICATION_INSIGHTS_NAME string = applicationInsightsName
output LOG_ANALYTICS_WORKSPACE_ID string = logAnalyticsWorkspaceId
output AZURE_POSTGRES_SERVER_FQDN string = '${postgresServerName}.postgres.database.azure.com'
output POSTGRES_SERVER_NAME string = postgresServerName
output POSTGRES_SERVER_LOCATION string = location
output POSTGRES_DATABASE string = postgresDatabaseName
output AZURE_CONTAINER_APPS_ENVIRONMENT_ID string = containerAppsEnvironmentId
output CONTAINER_APPS_ENVIRONMENT_NAME string = containerAppsEnvironmentName
output BACKEND_CONTAINER_APP_ID string = backendContainerAppId
output BACKEND_CONTAINER_APP_NAME string = backendContainerAppName
output FRONTEND_CONTAINER_APP_ID string = frontendContainerAppId
output FRONTEND_CONTAINER_APP_NAME string = frontendContainerAppName
output PRIVATE_BACKEND_MANAGED_IDENTITY_NAME string = privateBackendManagedIdentityName
output PRIVATE_FRONTEND_MANAGED_IDENTITY_NAME string = privateFrontendManagedIdentityName
output BACKEND_IMAGE_REPOSITORY string = backendImageRepository
output FRONTEND_IMAGE_REPOSITORY string = frontendImageRepository
output STANDARD_AGENT_STORAGE_ACCOUNT_NAME string = standardAgentStorageAccountName
output STANDARD_AGENT_COSMOS_ACCOUNT_NAME string = standardAgentCosmosAccountName
output STANDARD_AGENT_SEARCH_NAME string = standardAgentSearchName
output PRIVATE_VNET_ID string = resourceId('Microsoft.Network/virtualNetworks', privateVnetName)
output PRIVATE_VNET_NAME string = privateVnetName
output FOUNDRY_AGENT_SUBNET_ID string = '${resourceId('Microsoft.Network/virtualNetworks', privateVnetName)}/subnets/${foundryAgentSubnetName}'
output CONTAINER_APPS_INFRASTRUCTURE_SUBNET_ID string = '${resourceId('Microsoft.Network/virtualNetworks', privateVnetName)}/subnets/${containerAppsSubnetName}'
output PRIVATE_ENDPOINT_SUBNET_ID string = '${resourceId('Microsoft.Network/virtualNetworks', privateVnetName)}/subnets/${privateEndpointSubnetName}'
output PRIVATE_RUNNER_SUBNET_ID string = '${resourceId('Microsoft.Network/virtualNetworks', privateVnetName)}/subnets/${privateRunnerSubnetName}'
output PRIVATE_RUNNER_VM_ID string = resourceId('Microsoft.Compute/virtualMachines', privateRunnerVmName)
output PRIVATE_RUNNER_VM_NAME string = privateRunnerVmName
output API_BASE_URL string = 'https://${reference(backendContainerAppId, '2025-01-01').configuration.ingress.fqdn}'
output WEB_URL string = 'https://${reference(frontendContainerAppId, '2025-01-01').configuration.ingress.fqdn}'
