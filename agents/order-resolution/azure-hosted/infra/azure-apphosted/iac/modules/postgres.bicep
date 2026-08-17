targetScope = 'resourceGroup'

param location string
param postgresServerName string
param postgresDatabaseName string
param serverAdministratorLogin string
@secure()
param serverAdministratorPassword string
param administratorObjectId string
param administratorPrincipalName string
param administratorPrincipalType string
param operatorIp string = ''
param tags object = {}

resource server 'Microsoft.DBforPostgreSQL/flexibleServers@2024-08-01' = {
  name: postgresServerName
  location: location
  tags: tags
  sku: {
    name: 'Standard_D2ds_v5'
    tier: 'GeneralPurpose'
  }
  properties: {
    administratorLogin: serverAdministratorLogin
    administratorLoginPassword: serverAdministratorPassword
    version: '16'
    storage: {
      storageSizeGB: 128
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Enabled'
      tenantId: subscription().tenantId
    }
    network: {
      publicNetworkAccess: 'Enabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
  }
}

resource administrator 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2024-08-01' = {
  parent: server
  name: administratorObjectId
  properties: {
    principalName: administratorPrincipalName
    principalType: administratorPrincipalType
    tenantId: subscription().tenantId
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2024-08-01' = {
  parent: server
  name: postgresDatabaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// Public-POC compromise only. Production must use private networking or
// deterministic controlled egress before increasing backend replicas.
resource azureServicesFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = {
  parent: server
  name: 'public-poc-allow-azure-services'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

resource operatorFirewall 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2024-08-01' = if (!empty(operatorIp)) {
  parent: server
  name: 'allow-schema-operator'
  properties: {
    startIpAddress: operatorIp
    endIpAddress: operatorIp
  }
}

output serverName string = server.name
output serverFqdn string = server.properties.fullyQualifiedDomainName
output databaseName string = database.name
