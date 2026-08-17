targetScope = 'resourceGroup'

@description('Existing Underwriting Foundry account name.')
param foundryAccountName string

@description('Existing Underwriting Foundry project name.')
param foundryProjectName string

@description('Resource location recorded in connection metadata.')
param location string

@description('Deterministic project CustomKeys connection name.')
param runtimeConnectionName string = 'underwritingruntimesecrets'

@secure()
@description('Hosted runtime PostgreSQL URL stored in the project CustomKeys connection.')
param runtimeDatabaseUrl string

module runtimeSecretConnection './modules/underwriting-runtime-secret-connection.bicep' = {
  name: 'underwriting-runtime-secret-connection'
  params: {
    accountName: foundryAccountName
    projectName: foundryProjectName
    location: location
    runtimeConnectionName: runtimeConnectionName
    runtimeDatabaseUrl: runtimeDatabaseUrl
  }
}

output FOUNDRY_RUNTIME_CONNECTION_NAME string = runtimeSecretConnection.outputs.connectionName
