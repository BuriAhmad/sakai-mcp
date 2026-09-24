@description('Azure region for every Sakai resource.')
param location string = resourceGroup().location

@description('Administrator SSH public key, supplied at deployment time.')
param adminSshPublicKey string

@description('Single trusted administrator CIDR for SSH, for example 203.0.113.10/32.')
param adminSourceCidr string

@secure()
@description('Azure MySQL administrator password. Never commit this value.')
param mysqlAdminPassword string

@description('Deliberate globally unique MySQL Flexible Server name.')
param mysqlServerName string = 'mysql-sakai-dev-55a5701c-uae'

@description('Deliberate globally unique public DNS label for the Sakai VM.')
param publicDnsLabel string = 'sakai-mcp-dev-55a5701c'

@description('VM administrator username.')
param vmAdminUsername string = 'sakaiadmin'

@description('Low-cost 8 GiB burstable VM size. This may be adjusted only to an equivalent 8 GiB B-series SKU for regional capacity.')
param vmSize string = 'Standard_B2s_v2'

param tags object = {
  project: 'sakai-mcp'
  environment: 'dev'
  purpose: 'lms-sandbox'
  owner: 'burhan'
  'managed-by': 'bicep'
}

var vnetName = 'vnet-sakai-dev'
var appSubnetName = 'snet-sakai-app-dev'
var mysqlSubnetName = 'snet-sakai-mysql-dev'
var nsgName = 'nsg-sakai-app-dev'
var pipName = 'pip-sakai-dev'
var nicName = 'nic-sakai-dev'
var vmName = 'vm-sakai-dev'
var privateDnsZoneName = 'private.mysql.database.azure.com'

resource appNsg 'Microsoft.Network/networkSecurityGroups@2024-01-01' = {
  name: nsgName
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'allow-https'
        properties: {
          priority: 100
          protocol: 'Tcp'
          access: 'Allow'
          direction: 'Inbound'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '443'
        }
      }
      {
        name: 'allow-http-redirect'
        properties: {
          priority: 110
          protocol: 'Tcp'
          access: 'Allow'
          direction: 'Inbound'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '80'
        }
      }
      {
        name: 'allow-ssh-admin-only'
        properties: {
          priority: 120
          protocol: 'Tcp'
          access: 'Allow'
          direction: 'Inbound'
          sourceAddressPrefix: adminSourceCidr
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '22'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.42.0.0/16'
      ]
    }
    subnets: [
      {
        name: appSubnetName
        properties: {
          addressPrefix: '10.42.1.0/24'
          networkSecurityGroup: {
            id: appNsg.id
          }
        }
      }
      {
        name: mysqlSubnetName
        properties: {
          addressPrefix: '10.42.2.0/24'
          delegations: [
            {
              name: 'mysql-flexible-server'
              properties: {
                serviceName: 'Microsoft.DBforMySQL/flexibleServers'
              }
            }
          ]
        }
      }
    ]
  }
}

resource privateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: privateDnsZoneName
  location: 'global'
  tags: tags
}

resource privateDnsVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: privateDnsZone
  name: '${vnetName}-link'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

resource mysqlServer 'Microsoft.DBforMySQL/flexibleServers@2023-12-30' = {
  name: mysqlServerName
  location: location
  tags: tags
  sku: {
    name: 'Standard_B1ms'
    tier: 'Burstable'
  }
  properties: {
    administratorLogin: 'sakaiadmin'
    administratorLoginPassword: mysqlAdminPassword
    version: '8.0.21'
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
    highAvailability: {
      mode: 'Disabled'
    }
    storage: {
      storageSizeGB: 20
      autoGrow: 'Disabled'
      iops: 360
    }
    network: {
      delegatedSubnetResourceId: resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, mysqlSubnetName)
      privateDnsZoneResourceId: privateDnsZone.id
      publicNetworkAccess: 'Disabled'
    }
  }
  dependsOn: [
    privateDnsVnetLink
  ]
}

resource publicIp 'Microsoft.Network/publicIPAddresses@2024-01-01' = {
  name: pipName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
    dnsSettings: {
      domainNameLabel: publicDnsLabel
    }
  }
}

resource nic 'Microsoft.Network/networkInterfaces@2024-01-01' = {
  name: nicName
  location: location
  tags: tags
  properties: {
    ipConfigurations: [
      {
        name: 'ipconfig1'
        properties: {
          privateIPAllocationMethod: 'Dynamic'
          subnet: {
            id: resourceId('Microsoft.Network/virtualNetworks/subnets', vnet.name, appSubnetName)
          }
          publicIPAddress: {
            id: publicIp.id
          }
        }
      }
    ]
  }
}

resource vm 'Microsoft.Compute/virtualMachines@2024-03-01' = {
  name: vmName
  location: location
  tags: tags
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    osProfile: {
      computerName: vmName
      adminUsername: vmAdminUsername
      linuxConfiguration: {
        disablePasswordAuthentication: true
        ssh: {
          publicKeys: [
            {
              path: '/home/${vmAdminUsername}/.ssh/authorized_keys'
              keyData: adminSshPublicKey
            }
          ]
        }
      }
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'ubuntu-24_04-lts'
        sku: 'server'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: 'StandardSSD_LRS'
        }
        diskSizeGB: 64
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic.id
          properties: {
            primary: true
          }
        }
      ]
    }
  }
}

resource autoShutdown 'Microsoft.DevTestLab/schedules@2018-09-15' = {
  name: 'shutdown-computevm-${vm.name}'
  location: location
  tags: tags
  properties: {
    status: 'Enabled'
    taskType: 'ComputeVmShutdownTask'
    dailyRecurrence: {
      time: '1900'
    }
    timeZoneId: 'Pakistan Standard Time'
    targetResourceId: vm.id
    notificationSettings: {
      status: 'Disabled'
      timeInMinutes: 30
    }
  }
}

output resourceGroupName string = resourceGroup().name
output vmName string = vm.name
output mysqlServerName string = mysqlServer.name
output mysqlFqdn string = '${mysqlServer.name}.mysql.database.azure.com'
output publicFqdn string = '${publicDnsLabel}.${location}.cloudapp.azure.com'
output vnetId string = vnet.id
