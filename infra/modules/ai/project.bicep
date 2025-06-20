@description('The AI Foundry Project name')
param name string

@description('The name of the AI Foundry Resource where this project should be connected')
param aiFoundryName string

// @description('The public network access setting to use for the AI Studio Hub Resource')
// @allowed(['Enabled', 'Disabled'])
// param publicNetworkAccess string = 'Enabled'

param location string = resourceGroup().location

param tags object = {}

resource aiFoundryResource 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiFoundryName
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  // parent: aiFoundryResource
  // name: name
  name: '${aiFoundryName}/${name}'
  location: location
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  // properties: {
    // description: 'Default project created with the resource'
    // displayName: 'rh05-manual-prj'
  // }
  properties: {}
}

@description('The resource id of the AI Project Hub Resource')
output resourceId string = project.id

@description('Azure AI Foundry project full name')
output full_name string = project.name

@description('Azure AI Foundry project short name')
output name string = name

// @description('Azure AI Foundry project connection string')
// output connectionString string = '${split(project.properties.endpoints['0'].url, '/')[2]};${subscription().subscriptionId};${resourceGroup().name};${project.name}'
