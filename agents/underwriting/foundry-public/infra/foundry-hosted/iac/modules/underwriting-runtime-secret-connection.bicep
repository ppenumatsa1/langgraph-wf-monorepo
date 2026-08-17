@description('Name of the existing Underwriting Foundry account.')
param accountName string

@description('Name of the existing Underwriting Foundry project.')
param projectName string

@description('Location recorded in connection metadata.')
param location string

@description('Deterministic project CustomKeys connection name.')
param runtimeConnectionName string = 'underwritingruntimesecrets'

@secure()
@description('Hosted runtime PostgreSQL URL stored under the database_url custom key.')
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
      target: 'https://underwriting-runtime-secrets.local'
      credentials: {
        keys: {
          database_url: runtimeDatabaseUrl
        }
      }
      metadata: {
        ApiType: 'KeyValue'
        location: location
        purpose: 'underwriting-hosted-runtime-secrets'
      }
    }
  }
}

output connectionName string = runtimeConnectionName
