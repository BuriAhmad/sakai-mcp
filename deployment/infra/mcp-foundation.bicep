@description('MCP resources are colocated with the existing Sakai VM in Korea Central.')
param location string = 'koreacentral'

param tags object = {
  project: 'sakai-mcp'
  environment: 'dev'
  purpose: 'lms-sandbox'
  owner: 'burhan'
  'managed-by': 'bicep'
}

var suffix = uniqueString(resourceGroup().id)
var registryName = 'acrsmcpdev${suffix}'
var vaultName = 'kvsmcp${suffix}'

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: location
  tags: tags
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
    networkRuleBypassOptions: 'None'
  }
}

resource vault 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: vaultName
  location: location
  tags: tags
  properties: {
    tenantId: tenant().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    enableRbacAuthorization: true
    enablePurgeProtection: true
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      bypass: 'None'
      defaultAction: 'Allow'
    }
  }
}

resource workspace 'Microsoft.OperationalInsights/workspaces@2025-07-01' = {
  name: 'log-mcp-sakai-dev'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    workspaceCapping: {
      dailyQuotaGb: 1
    }
  }
}

resource environment 'Microsoft.App/managedEnvironments@2025-07-01' = {
  name: 'cae-mcp-sakai-dev'
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

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-mcp-sakai-dev'
  location: location
  tags: tags
}

resource registryPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, 'AcrPull')
  scope: registry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource vaultSecretsUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, identity.id, 'KeyVaultSecretsUser')
  scope: vault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

output registryName string = registry.name
output registryLoginServer string = registry.properties.loginServer
output vaultName string = vault.name
output vaultUri string = vault.properties.vaultUri
output environmentName string = environment.name
output identityId string = identity.id
