@description('Name of the existing Foundry account.')
param accountName string

@description('Name of the existing Foundry project.')
param projectName string

@description('Location used for connection metadata.')
param location string

@description('Deterministic project connection name for hosted runtime secrets.')
param runtimeConnectionName string = 'orderresolutionruntimesecrets'

@secure()
@description('Hosted runtime PostgreSQL URL stored as the database_url custom key.')
param runtimeDatabaseUrl string

resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: accountName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  parent: account
  name: projectName

  resource runtimeSecretConnection 'connections@2025-04-01-preview' = {
    name: runtimeConnectionName
    properties: {
      category: 'CustomKeys'
      authType: 'CustomKeys'
      target: 'https://runtime-secrets.local'
      credentials: {
        keys: {
          database_url: runtimeDatabaseUrl
        }
      }
      metadata: {
        ApiType: 'KeyValue'
        location: location
      }
    }
  }
}

output runtimeConnectionName string = runtimeConnectionName
