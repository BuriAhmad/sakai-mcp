@description('Deploy an immutable ACR digest, for example registry.azurecr.io/sakai-mcp@sha256:...')
@minLength(80)
param image string

@description('Full 40-character source commit used to build the image.')
@minLength(40)
@maxLength(40)
param sourceCommit string

@description('SHA-256 of the dependency lockfile used to build the image.')
@minLength(64)
@maxLength(64)
param lockSha256 string

@description('Canonical public HTTPS origin of the Container App, without a trailing slash.')
param mcpPublicUrl string

@description('Canonical hostname bound directly to the Container App.')
param mcpHostname string = 'mcp.smartdigest.app'

@description('Azure-managed certificate created during the DNS-validated hostname bootstrap.')
param managedCertificateName string = 'mc-cae-mcp-sakai--mcp-smartdigest--7680'

@description('Verified Sakai HTTPS origin.')
param sakaiBaseUrl string

param entraTenantId string
param mcpResourceClientId string
param mcpIssuer string
param mcpAudience string
param mcpJwksUri string
param sakaiResourceClientId string
param sakaiAudience string

param location string = 'koreacentral'

param tags object = {
  project: 'sakai-mcp'
  environment: 'dev'
  purpose: 'lms-sandbox'
  owner: 'burhan'
  'managed-by': 'bicep'
}

var suffix = uniqueString(resourceGroup().id)

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: 'acrsmcpdev${suffix}'
}

resource vault 'Microsoft.KeyVault/vaults@2024-11-01' existing = {
  name: 'kvsmcp${suffix}'
}

resource environment 'Microsoft.App/managedEnvironments@2025-07-01' existing = {
  name: 'cae-mcp-sakai-dev'
}

resource mcpCertificate 'Microsoft.App/managedEnvironments/managedCertificates@2025-07-01' existing = {
  parent: environment
  name: managedCertificateName
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: 'id-mcp-sakai-dev'
}

resource app 'Microsoft.App/containerApps@2025-07-01' = {
  name: 'ca-mcp-sakai-dev'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identity.id}': {}
    }
  }
  properties: {
    managedEnvironmentId: environment.id
    configuration: {
      activeRevisionsMode: 'Single'
      maxInactiveRevisions: 3
      identitySettings: [
        {
          identity: identity.id
          lifecycle: 'None'
        }
      ]
      ingress: {
        external: true
        targetPort: 8000
        transport: 'http'
        allowInsecure: false
        customDomains: [
          {
            name: mcpHostname
            bindingType: 'SniEnabled'
            certificateId: mcpCertificate.id
          }
        ]
        stickySessions: {
          affinity: 'none'
        }
      }
      registries: [
        {
          server: registry.properties.loginServer
          identity: identity.id
        }
      ]
      secrets: [
        {
          name: 'obo-private-key'
          keyVaultUrl: '${vault.properties.vaultUri}secrets/obo-private-key'
          identity: identity.id
        }
        {
          name: 'obo-certificate'
          keyVaultUrl: '${vault.properties.vaultUri}secrets/obo-certificate'
          identity: identity.id
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'sakai-mcp'
          image: image
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          env: [
            { name: 'ENVIRONMENT', value: 'development' }
            { name: 'APP_COMMIT', value: sourceCommit }
            { name: 'APP_LOCK_SHA256', value: lockSha256 }
            { name: 'MCP_PUBLIC_URL', value: mcpPublicUrl }
            { name: 'SAKAI_BASE_URL', value: sakaiBaseUrl }
            { name: 'ENTRA_TENANT_ID', value: entraTenantId }
            { name: 'MCP_RESOURCE_CLIENT_ID', value: mcpResourceClientId }
            { name: 'MCP_ISSUER', value: mcpIssuer }
            { name: 'MCP_AUDIENCE', value: mcpAudience }
            { name: 'MCP_JWKS_URI', value: mcpJwksUri }
            { name: 'SAKAI_RESOURCE_CLIENT_ID', value: sakaiResourceClientId }
            { name: 'SAKAI_AUDIENCE', value: sakaiAudience }
            { name: 'OBO_PRIVATE_KEY_FILE', value: '/mnt/secrets/private-key.pem' }
            { name: 'OBO_CERTIFICATE_FILE', value: '/mnt/secrets/certificate.pem' }
          ]
          volumeMounts: [
            {
              volumeName: 'obo-credentials'
              mountPath: '/mnt/secrets'
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/live', port: 8000, scheme: 'HTTP' }
              initialDelaySeconds: 10
              periodSeconds: 30
              timeoutSeconds: 3
              failureThreshold: 3
            }
            {
              type: 'Readiness'
              httpGet: { path: '/ready', port: 8000, scheme: 'HTTP' }
              initialDelaySeconds: 5
              periodSeconds: 10
              timeoutSeconds: 3
              failureThreshold: 3
            }
          ]
        }
      ]
      volumes: [
        {
          name: 'obo-credentials'
          storageType: 'Secret'
          secrets: [
            { secretRef: 'obo-private-key', path: 'private-key.pem' }
            { secretRef: 'obo-certificate', path: 'certificate.pem' }
          ]
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 2
        rules: [
          {
            name: 'http-concurrency'
            http: {
              metadata: {
                concurrentRequests: '20'
              }
            }
          }
        ]
      }
    }
  }
}

output fqdn string = app.properties.configuration.ingress.fqdn
output revision string = app.properties.latestRevisionName
