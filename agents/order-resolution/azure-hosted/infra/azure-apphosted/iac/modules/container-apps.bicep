targetScope = 'resourceGroup'

param location string
param containerAppsEnvironmentName string
param logAnalyticsWorkspaceName string
param applicationInsightsName string
param containerRegistryName string
param backendContainerAppName string
param frontendContainerAppName string
param backendManagedIdentityName string
param frontendManagedIdentityName string
param foundryAccountName string
param foundryProjectName string
param foundryModelDeploymentName string
param tags object = {}

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' existing = {
  name: logAnalyticsWorkspaceName
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: applicationInsightsName
}

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: containerRegistryName
}

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' existing = {
  name: foundryAccountName
}

resource backendIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: backendManagedIdentityName
  location: location
  tags: tags
}

resource frontendIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: frontendManagedIdentityName
  location: location
  tags: tags
}

resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: containerAppsEnvironmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: workspace.properties.customerId
        sharedKey: workspace.listKeys().primarySharedKey
      }
    }
  }
}

resource acrPullRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
}

resource openAIUserRole 'Microsoft.Authorization/roleDefinitions@2022-04-01' existing = {
  scope: subscription()
  name: '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
}

resource backendAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, backendIdentity.id, acrPullRole.id)
  scope: registry
  properties: {
    roleDefinitionId: acrPullRole.id
    principalId: backendIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource frontendAcrPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, frontendIdentity.id, acrPullRole.id)
  scope: registry
  properties: {
    roleDefinitionId: acrPullRole.id
    principalId: frontendIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource backendFoundryInference 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(foundryAccount.id, backendIdentity.id, openAIUserRole.id)
  scope: foundryAccount
  properties: {
    roleDefinitionId: openAIUserRole.id
    principalId: backendIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource backend 'Microsoft.App/containerApps@2024-03-01' = {
  name: backendContainerAppName
  location: location
  tags: union(tags, {
    'azd-service-name': 'backend'
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${backendIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: false
        allowInsecure: false
        targetPort: 8000
        transport: 'http'
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: backendIdentity.id
        }
      ]
      secrets: [
        {
          name: 'appinsights-connection-string'
          value: appInsights.properties.ConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            {
              name: 'APP_ENV'
              value: 'azure-hosted'
            }
            {
              name: 'RUNTIME_TARGET'
              value: 'direct_langgraph'
            }
            {
              name: 'DB_SCHEMA_MANAGED_EXTERNALLY'
              value: 'true'
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: backendIdentity.properties.clientId
            }
            {
              name: 'AZURE_AI_PROJECT_ENDPOINT'
              value: 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${foundryProjectName}'
            }
            {
              name: 'FOUNDRY_PROJECTS_ENDPOINT'
              value: 'https://${foundryAccountName}.services.ai.azure.com/api/projects/${foundryProjectName}'
            }
            {
              name: 'FOUNDRY_MODEL_DEPLOYMENT_NAME'
              value: foundryModelDeploymentName
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'appinsights-connection-string'
            }
          ]
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/health'
                port: 8000
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              failureThreshold: 30
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 8000
              }
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        // Keep one backend replica until PostgreSQL-backed distributed
        // admission locking protects every LangGraph HITL resume.
        maxReplicas: 1
      }
    }
  }
  dependsOn: [
    backendAcrPull
    backendFoundryInference
  ]
}

resource frontend 'Microsoft.App/containerApps@2024-03-01' = {
  name: frontendContainerAppName
  location: location
  tags: union(tags, {
    'azd-service-name': 'frontend'
  })
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${frontendIdentity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        external: true
        allowInsecure: false
        targetPort: 5173
        transport: 'http'
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: frontendIdentity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'frontend'
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            {
              name: 'API_BASE'
              value: ''
            }
            {
              name: 'NGINX_API_UPSTREAM'
              value: 'https://${backend.properties.configuration.ingress.fqdn}'
            }
          ]
          probes: [
            {
              type: 'Startup'
              httpGet: {
                path: '/health'
                port: 5173
              }
              initialDelaySeconds: 5
              periodSeconds: 5
              failureThreshold: 30
            }
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: 5173
              }
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: {
                path: '/health'
                port: 5173
              }
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 3
      }
    }
  }
  dependsOn: [
    frontendAcrPull
  ]
}

output backendName string = backend.name
output frontendName string = frontend.name
output backendFqdn string = backend.properties.configuration.ingress.fqdn
output frontendFqdn string = frontend.properties.configuration.ingress.fqdn
