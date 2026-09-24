using '../main.bicep'

param location = 'koreacentral'
// Placeholder assignments satisfy Bicep parameter-file validation. deploy-infra.sh
// always overrides these values with local non-versioned deployment inputs.
param adminSshPublicKey = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDeploymentPlaceholderNotARealKey sakai-placeholder'
param adminSourceCidr = '192.0.2.1/32'
param mysqlAdminPassword = 'ReplaceMeWithLocalSecret123!'
// The original deterministic name has a Central India failed-operation reservation.
// This region-qualified suffix is the one and only UAE North server name.
param mysqlServerName = 'mysql-sakai-dev-55a5701c-uae'
param publicDnsLabel = 'sakai-mcp-dev-55a5701c'
param vmAdminUsername = 'sakaiadmin'
param vmSize = 'Standard_B2as_v2'
