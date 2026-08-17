targetScope = 'resourceGroup'

param location string
param foundryAccountName string
param foundryProjectName string
param applicationInsightsName string
param logAnalyticsWorkspaceName string
param tags object = {}

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}

resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource logAnalyticsReaderRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '73c42c96-874c-492b-b04d-ab87d138a893'
}

resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryAccountName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  tags: tags
  properties: {
    allowProjectManagement: true
    customSubDomainName: foundryAccountName
    disableLocalAuth: true
    publicNetworkAccess: 'Enabled'
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: account
  name: foundryProjectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: 'Model inference and report-only evaluation for the Azure-hosted LangGraph application.'
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: account
  name: 'order-resolution-gpt-4-1-mini'
  sku: {
    name: 'Standard'
    capacity: 100
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4.1-mini'
      version: '2025-04-14'
    }
    raiPolicyName: 'Microsoft.Default'
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

resource embeddingsDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: account
  name: 'order-resolution-text-embedding-3-small'
  sku: {
    name: 'Standard'
    capacity: 100
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'text-embedding-3-small'
      version: '1'
    }
    raiPolicyName: 'Microsoft.Default'
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
  dependsOn: [
    chatDeployment
  ]
}

resource evaluationDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: account
  name: 'order-resolution-gpt-4-1-mini-evaluation'
  sku: {
    name: 'Standard'
    capacity: 50
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4.1-mini'
      version: '2025-04-14'
    }
    raiPolicyName: 'Microsoft.Default'
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
  dependsOn: [
    embeddingsDeployment
  ]
}

resource projectApplicationInsightsReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(appInsights.id, project.id, logAnalyticsReaderRole.id)
  scope: appInsights
  properties: {
    roleDefinitionId: logAnalyticsReaderRole.id
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource projectLogAnalyticsReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(logAnalyticsWorkspace.id, project.id, logAnalyticsReaderRole.id)
  scope: logAnalyticsWorkspace
  properties: {
    roleDefinitionId: logAnalyticsReaderRole.id
    principalId: project.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  parent: project
  name: 'ApplicationInsights'
  properties: {
    category: 'AppInsights'
    target: appInsights.id
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: appInsights.properties.ConnectionString
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: appInsights.id
    }
  }
  dependsOn: [
    projectApplicationInsightsReader
    projectLogAnalyticsReader
  ]
}

output accountId string = account.id
output projectId string = project.id
output projectEndpoint string = 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${foundryProjectName}'
