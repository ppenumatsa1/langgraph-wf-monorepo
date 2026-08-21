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

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-11-15' existing = {
  name: cosmosAccountName
}

resource storageBlobDataOwnerRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
}

var cosmosDataContributorRoleId = '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
var cosmosAgentDataScope = '${cosmosAccount.id}/dbs/enterprise_memory'
var storageAgentContainerCondition = '((!(ActionMatches{\'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/tags/read\'}) AND !(ActionMatches{\'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/filter/action\'}) AND !(ActionMatches{\'Microsoft.Storage/storageAccounts/blobServices/containers/blobs/tags/write\'})) OR (@Resource[Microsoft.Storage/storageAccounts/blobServices/containers:name] StringStartsWithIgnoreCase \'${projectWorkspaceId}\' AND @Resource[Microsoft.Storage/storageAccounts/blobServices/containers:name] StringLikeIgnoreCase \'*-azureml-agent\'))'

resource storageAgentContainerOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, projectPrincipalId, storageBlobDataOwnerRole.id, projectWorkspaceId)
  scope: storageAccount
  properties: {
    roleDefinitionId: storageBlobDataOwnerRole.id
    principalId: projectPrincipalId
    principalType: 'ServicePrincipal'
    conditionVersion: '2.0'
    condition: storageAgentContainerCondition
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
