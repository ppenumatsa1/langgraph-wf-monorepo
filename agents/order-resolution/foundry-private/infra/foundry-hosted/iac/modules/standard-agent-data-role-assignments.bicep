targetScope = 'resourceGroup'

@description('Name of the private standard-agent storage account.')
param storageAccountName string

@description('Name of the private standard-agent Cosmos DB account.')
param cosmosAccountName string

@description('System-assigned principal ID of the Foundry project.')
param projectPrincipalId string

@description('Formatted internal workspace ID emitted by the Foundry project.')
param projectWorkspaceId string

resource storageAccount 'Microsoft.Storage/storageAccounts@2024-01-01' existing = {
  name: storageAccountName
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2024-01-01' existing = {
  parent: storageAccount
  name: 'default'
}

resource azureMlBlobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' existing = {
  parent: blobService
  name: '${projectWorkspaceId}-azureml-blobstore'
}

resource agentsBlobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' existing = {
  parent: blobService
  name: '${projectWorkspaceId}-agents-blobstore'
}

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = {
  name: cosmosAccountName
}

resource storageBlobDataContributorRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
}

resource storageBlobDataOwnerRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
}

var cosmosDataContributorRoleId = '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
var cosmosAgentDataScope = '${cosmosAccount.id}/dbs/enterprise_memory'

resource azureMlBlobContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(azureMlBlobContainer.id, projectPrincipalId, storageBlobDataContributorRole.id)
  scope: azureMlBlobContainer
  properties: {
    roleDefinitionId: storageBlobDataContributorRole.id
    principalId: projectPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource agentsBlobOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(agentsBlobContainer.id, projectPrincipalId, storageBlobDataOwnerRole.id)
  scope: agentsBlobContainer
  properties: {
    roleDefinitionId: storageBlobDataOwnerRole.id
    principalId: projectPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource cosmosDataContributor 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2022-05-15' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, projectPrincipalId, cosmosDataContributorRoleId)
  properties: {
    principalId: projectPrincipalId
    roleDefinitionId: cosmosDataContributorRoleId
    scope: cosmosAgentDataScope
  }
}
