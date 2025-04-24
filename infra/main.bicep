metadata name = 'az-ai-kickstarter'
metadata description = 'Deploys the infrastructure for Azure AI App Kickstarter'
metadata author = 'AI GBB EMEA <eminkevich@microsoft.com>; <dobroegl@microsoft.com>'

/* -------------------------------------------------------------------------- */
/*                                 PARAMETERS                                 */
/* -------------------------------------------------------------------------- */

@minLength(1)
@maxLength(64)
@description('Name of the environment which is used to generate a short unique hash used in all resources.')
param environmentName string

@description('Principal ID of the user running the deployment')
param azurePrincipalId string

@description('Location for all resources')
param location string

@description('Extra tags to be applied to provisioned resources')
param extraTags object = {}

@description('If true, deploy Azure AI Search Service')
param useAiSearch bool = false

@description('If true, use and setup authentication with Azure Entra ID')
param useAuthentication bool = false

@description('Set to true to use an existing Azure OpenAI service.In that case you will need to provide azureOpenAiEndpoint, azureOpenAiApiVersion, executorAzureOpenAiDeploymentName and utilityAzureOpenAiDeploymentName. Defaults to false.')
param useExistingAzureOpenAi bool = false

@description('Set to true to use an existing Azure AI Search service.In that case you will need to provide TODO. Defaults to false.')
param useExistingAiSearch bool = false

/* -----------------------  Azure Open AI  service ------------------------- */

// See also https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/models?tabs=global-standard%2Cstandard-chat-completions#availability-1
@description('Location for the OpenAI resource group')
@metadata({
  azd: {
    type: 'location'
  }
})
param azureOpenAiLocation string = ''

/* -------- Optional externally provided Azure OpenAI configuration -------- */

@description('Optional. The name of the Azure OpenAI resource to reuse. Used only if useExistingAzureOpenAi is true.')
param azureOpenAiName string = ''

@description('Optional. The endpoint of the Azure OpenAI resource to reuse. Used only if useExistingAzureOpenAi is true.')
param azureOpenAiEndpoint string = ''

@description('Optional. The API version of the Azure OpenAI resource to reuse. Used only if useExistingAzureOpenAi is true.')
param azureOpenAiApiVersion string = ''

@description('Optional. The name of the Azure OpenAI deployment for the executor to reuse. Used only if useExistingAzureOpenAi is true.')
param executorAzureOpenAiDeploymentName string = ''

@description('Optional. The name of the Azure OpenAI deployment for the utility to reuse. Used only if useExistingAzureOpenAi is true.')
param utilityAzureOpenAiDeploymentName string = ''

@description('The Azure OpenAI service resource group name to reuse. Optional: Needed only if resource group is different from current resource group.')
param azureOpenAiResourceGroupName string = ''

/* -----------------------  Azure AI search service ------------------------ */

@description('Optional. Defines the SKU of an Azure AI Search Service, which determines price tier and capacity limits.')
@allowed([
  'basic'
  'free'
  'standard'
  'standard2'
  'standard3'
  'storage_optimized_l1'
  'storage_optimized_l2'
])
param aiSearchSkuName string = 'basic'

// See https://learn.microsoft.com/en-us/azure/search/search-region-support
@description('Location for the Azure OpenAI Service. Optional: needed only if Azure OpenAI is deployed in a different location than the rest of the resources.')
@metadata({
  azd: {
    type: 'location'
  }
})
param azureAiSearchLocation string = ''

@description('Name of the Azure AI Search Service to deploy. Optional: needed if useExistingAiSearchService is true or you want a custom azureAiSearchName.')
param azureAiSearchName string = ''

@description('The Azure AI Search service resource group name to reuse. Optional: Needed only if resource group is different from current resource group.')
param azureAiSearchResourceGroupName string = ''

/* ---------------------------- Shared Resources ---------------------------- */

@maxLength(63)
@description('Name of the log analytics workspace to deploy. If not specified, a name will be generated. The maximum length is 63 characters.')
param logAnalyticsWorkspaceName string = ''

@maxLength(255)
@description('Name of the application insights to deploy. If not specified, a name will be generated. The maximum length is 255 characters.')
param applicationInsightsName string = ''

@description('Application Insights Location')
param appInsightsLocation string = location

@description('The auth tenant id for the app (leave blank in AZD to use your current tenant)')
param authTenantId string = '' // Make sure authTenantId is set if not using AZD

@description('Name of the authentication client secret in the key vault')
param authClientSecretName string = 'AZURE-AUTH-CLIENT-SECRET'

@description('The auth client id for the frontend and backend app')
param authClientAppId string = ''

@description('Client secret of the authentication client')
@secure()
param authClientSecret string = ''

@maxLength(50)
@description('Name of the container registry to deploy. If not specified, a name will be generated. The name is global and must be unique within Azure. The maximum length is 50 characters.')
param containerRegistryName string = ''

@maxLength(60)
@description('Name of the container apps environment to deploy. If not specified, a name will be generated. The maximum length is 60 characters.')
param containerAppsEnvironmentName string = ''

/* -------------------------------- Frontend -------------------------------- */

@maxLength(32)
@description('Name of the frontend container app to deploy. If not specified, a name will be generated. The maximum length is 32 characters.')
param frontendContainerAppName string = ''

@description('Set if the frontend container app already exists.')
param frontendExists bool = false

/* --------------------------------- Backend -------------------------------- */

@maxLength(32)
@description('Name of the backend container app to deploy. If not specified, a name will be generated. The maximum length is 32 characters.')
param backendContainerAppName string = ''

@description('Set if the backend container app already exists.')
param backendExists bool = false

/* -------------------------------------------------------------------------- */
/*                                  VARIABLES                                 */
/* -------------------------------------------------------------------------- */

// Load abbreviations from JSON file
var abbreviations = loadJsonContent('./abbreviations.json')

@description('Generate a unique token to make global resource names unique')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))

@description('Name of the environment with only alphanumeric characters. Used for resource names that require alphanumeric characters only')
var alphaNumericEnvironmentName = replace(replace(environmentName, '-', ''), ' ', '')

@description('Tags to be applied to all provisioned resources')
var tags = union(
  {
    'azd-env-name': environmentName
    solution: 'az-ai-kickstarter'
  },
  extraTags
)

/* --------------------- Globally Unique Resource Names --------------------- */

var _applicationInsightsName = !empty(applicationInsightsName)
  ? applicationInsightsName
  : take('${abbreviations.insightsComponents}${environmentName}', 255)
var _logAnalyticsWorkspaceName = !empty(logAnalyticsWorkspaceName)
  ? logAnalyticsWorkspaceName
  : take('${abbreviations.operationalInsightsWorkspaces}${environmentName}', 63)

var _storageAccountName = take(
  '${abbreviations.storageStorageAccounts}${alphaNumericEnvironmentName}${resourceToken}',
  24
)
var _azureOpenAiName = useExistingAzureOpenAi
  ? azureOpenAiName // if reusing existing service, use the provided name
  : (empty(azureOpenAiName) // else use only if not empty to override the default name
      ? take('${abbreviations.cognitiveServicesOpenAI}${alphaNumericEnvironmentName}${resourceToken}', 63)
      : azureOpenAiName)

var _aiHubName = take('${abbreviations.aiPortalHub}${environmentName}', 260)
var _aiProjectName = take('${abbreviations.aiPortalProject}${environmentName}', 260)

var _azureAiSearchName = useExistingAiSearch
  ? azureAiSearchName // if reusing existing service, use the provided name
  : (empty(azureAiSearchName) // else use only if not empty to override the default name
      ? take('${abbreviations.searchSearchServices}${environmentName}', 260)
      : azureAiSearchName)

var _containerRegistryName = !empty(containerRegistryName)
  ? containerRegistryName
  : take('${abbreviations.containerRegistryRegistries}${alphaNumericEnvironmentName}${resourceToken}', 50)
var _keyVaultName = take('${abbreviations.keyVaultVaults}${alphaNumericEnvironmentName}-${resourceToken}', 24)
var _containerAppsEnvironmentName = !empty(containerAppsEnvironmentName)
  ? containerAppsEnvironmentName
  : take('${abbreviations.appManagedEnvironments}${environmentName}', 60)

/* ----------------------------- Resource Names ----------------------------- */

// These resources only require uniqueness within resource group
var _appIdentityName = take('${abbreviations.managedIdentityUserAssignedIdentities}app-${environmentName}', 32)
var _frontendContainerAppName = empty(frontendContainerAppName)
  ? take('${abbreviations.appContainerApps}frontend-${environmentName}', 32)
  : frontendContainerAppName
var _backendContainerAppName = empty(backendContainerAppName)
  ? take('${abbreviations.appContainerApps}backend-${environmentName}', 32)
  : backendContainerAppName

// ------------------------
// Order is important:
// 1. Executor
// 2. Utility
@description('Model deployment configurations')
var deployments = loadYamlContent('./deployments.yaml')

var _azureOpenAiEndpoint = useExistingAzureOpenAi ? azureOpenAiEndpoint : aiServices.outputs.endpoint

@description('Azure OpenAI API Version')
var _azureOpenAiApiVersion = empty(azureOpenAiApiVersion) ? '2024-12-01-preview' : azureOpenAiApiVersion

@description('Azure OpenAI Model Deployment Name - Executor Service')
var _executorAzureOpenAiDeploymentName = !empty(executorAzureOpenAiDeploymentName)
  ? executorAzureOpenAiDeploymentName
  : deployments[0].name

@description('Azure OpenAI Model Deployment Name - Utility Service')
var _utilityAzureOpenAiDeploymentName = !empty(utilityAzureOpenAiDeploymentName)
  ? utilityAzureOpenAiDeploymentName
  : deployments[1].name

var _azureAiSearchLocation = empty(azureAiSearchLocation) ? location : azureAiSearchLocation
var _azureAiSearchEndpoint = 'https://${_azureAiSearchName}.search.windows.net'

/* -------------------------------------------------------------------------- */
/*                                  RESOURCES                                 */
/* -------------------------------------------------------------------------- */

/* ------------------------------- AI Foundry  ------------------------------ */

module aiHub 'modules/ai/hub.bicep' = {
  name: '${deployment().name}-aiHub'
  params: {
    location: location
    tags: tags
    name: _aiHubName
    displayName: _aiHubName
    keyVaultId: app.outputs.keyVaultResourceId
    storageAccountId: storageAccount.outputs.resourceId
    containerRegistryId: app.outputs.containerRegistryResourceId
    applicationInsightsId: appInsightsComponent.outputs.resourceId
    openAiName: useExistingAzureOpenAi ? azureOpenAiName : _azureOpenAiName
    azureOpenAiResourceGroupName: useExistingAzureOpenAi ? azureOpenAiResourceGroupName : ''
    openAiConnectionName: 'aoai-connection'

    aiSearchName: useAiSearch ? _azureAiSearchName : ''
    azureAiSearchResourceGroupName: useAiSearch ? azureAiSearchResourceGroupName : ''
    aiSearchConnectionName: 'search-service-connection'
  }
}

module aiProject 'modules/ai/project.bicep' = {
  name: '${deployment().name}-aiProject'
  params: {
    location: location
    tags: tags
    name: _aiProjectName
    displayName: _aiProjectName
    hubName: aiHub.outputs.name
  }
}

module storageAccount 'br/public:avm/res/storage/storage-account:0.19.0' = {
  name: '${deployment().name}-storageAccount'
  scope: resourceGroup()
  params: {
    location: location
    tags: tags
    name: _storageAccountName
    kind: 'StorageV2'
    blobServices: {
      corsRules: [
        {
          allowedOrigins: [
            'https://mlworkspace.azure.ai'
            'https://ml.azure.com'
            'https://*.ml.azure.com'
            'https://ai.azure.com'
            'https://*.ai.azure.com'
            'https://mlworkspacecanary.azure.ai'
            'https://mlworkspace.azureml-test.net'
          ]
          allowedMethods: [
            'GET'
            'HEAD'
            'POST'
            'PUT'
            'DELETE'
            'OPTIONS'
            'PATCH'
          ]
          maxAgeInSeconds: 1800
          exposedHeaders: [
            '*'
          ]
          allowedHeaders: [
            '*'
          ]
        }
      ]
      containers: [
        {
          name: 'default'
          roleAssignments: [
            {
              roleDefinitionIdOrName: 'Storage Blob Data Contributor'
              principalId: appIdentity.outputs.principalId
              principalType: 'ServicePrincipal'
            }
          ]
        }
      ]
      roleAssignments: [
        {
          roleDefinitionIdOrName: 'Storage Blob Data Contributor'
          principalId: azurePrincipalId
        }
      ]
      deleteRetentionPolicy: {
        allowPermanentDelete: false
        enabled: false
      }
      shareDeleteRetentionPolicy: {
        enabled: true
        days: 7
      }
    }
  }
}

module aiServices 'br/public:avm/res/cognitive-services/account:0.10.2' = if (!useExistingAzureOpenAi) {
  name: '${deployment().name}-aiServices'
  params: {
    name: _azureOpenAiName
    location: empty(azureOpenAiLocation) ? location : azureOpenAiLocation
    tags: tags
    kind: 'AIServices'
    customSubDomainName: _azureOpenAiName
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
    disableLocalAuth: false
    sku: 'S0'
    deployments: deployments
    diagnosticSettings: [
      {
        name: 'customSetting'
        logCategoriesAndGroups: [
          {
            category: 'RequestResponse'
          }
          {
            category: 'Audit'
          }
        ]
        metricCategories: [
          {
            category: 'AllMetrics'
          }
        ]
        workspaceResourceId: logAnalyticsWorkspace.outputs.resourceId
      }
    ]
    roleAssignments: [
      // See also https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/faq
      {
        roleDefinitionIdOrName: 'Cognitive Services OpenAI User'
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: 'Cognitive Services User'
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: 'Cognitive Services OpenAI Contributor'
        principalId: azurePrincipalId
        principalType: 'User'
      }
      {
        principalId: azurePrincipalId
        roleDefinitionIdOrName: 'Cognitive Services User'
        principalType: 'User'
      }
      {
        // required for Document Intelligence Studio
        roleDefinitionIdOrName: 'Contributor'
        principalId: azurePrincipalId
        principalType: 'User'
      }
    ]
  }
}

module aiSearchService 'br/public:avm/res/search/search-service:0.9.2' = if (useAiSearch && !useExistingAiSearch) {
  name: '${deployment().name}-aiSearchService'
  scope: resourceGroup()
  params: {
    name: _azureAiSearchName
    location: _azureAiSearchLocation
    tags: tags
    sku: aiSearchSkuName
    partitionCount: 1
    replicaCount: 1
    roleAssignments: [
      // See also https://learn.microsoft.com/en-us/azure/search/search-security-rbac
      {
        roleDefinitionIdOrName: 'Search Index Data Contributor'
        principalId: appIdentity.outputs.principalId
        principalType: 'ServicePrincipal'
      }
      {
        roleDefinitionIdOrName: 'Search Index Data Contributor'
        principalId: azurePrincipalId
        principalType: 'User'
      }
      {
        roleDefinitionIdOrName: 'Search Service Contributor'
        principalId: azurePrincipalId
        principalType: 'User'
      }
    ]
  }
}
/* --------------------------------- App  ----------------------------------- */

module appIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.4.1' = {
  name: '${deployment().name}-appIdentity'
  scope: resourceGroup()
  params: {
    name: _appIdentityName
    location: location
    tags: tags
  }
}

module app 'modules/app.bicep' = {
  name: '${deployment().name}-app'
  params: {
    location: location
    tags: tags
    appIdentityName: _appIdentityName
    appInsightsConnectionString: appInsightsComponent.outputs.connectionString
    authClientAppId: authClientAppId
    authClientSecret: authClientSecret
    authClientSecretName: authClientSecretName
    authTenantId: authTenantId
    azureOpenAiApiVersion: _azureOpenAiApiVersion
    azureOpenAiEndpoint: _azureOpenAiEndpoint
    azurePrincipalId: azurePrincipalId
    backendContainerAppName: _backendContainerAppName
    backendExists: backendExists
    containerAppsEnvironmentName: _containerAppsEnvironmentName
    containerRegistryName: _containerRegistryName
    executorAzureOpenAiDeploymentName: _executorAzureOpenAiDeploymentName
    frontendContainerAppName: _frontendContainerAppName
    frontendExists: frontendExists
    keyVaultName: _keyVaultName
    logAnalyticsWorkspaceResourceId: logAnalyticsWorkspace.outputs.resourceId
    useAuthentication: useAuthentication
    utilityAzureOpenAiDeploymentName: _utilityAzureOpenAiDeploymentName
  }
}

/* ------------------------------ CosmosDB  --------------------------------- */

/* module cosmosDbAccount 'br/public:avm/res/document-db/database-account:0.12.0' = {
  name: '${deployment().name}-cosmosDbAccount'
  params: {
    name: 'dddamin001'
    location: location
    sqlRoleAssignmentsPrincipalIds: [
      azurePrincipalId
      appIdentity.outputs.principalId
    ]
  }
} */

/* ---------------------------- Observability  ------------------------------ */

module logAnalyticsWorkspace 'br/public:avm/res/operational-insights/workspace:0.11.1' = {
  name: '${deployment().name}-workspaceDeployment'
  params: {
    name: _logAnalyticsWorkspaceName
    location: location
    tags: tags
    dataRetention: 30
  }
}

module appInsightsComponent 'br/public:avm/res/insights/component:0.6.0' = {
  name: '${deployment().name}-applicationInsights'
  params: {
    name: _applicationInsightsName
    location: appInsightsLocation
    workspaceResourceId: logAnalyticsWorkspace.outputs.resourceId
  }
}

/* -------------------------------------------------------------------------- */
/*                                   OUTPUTS                                  */
/* -------------------------------------------------------------------------- */

// Outputs are automatically saved in the local azd environment .env file.
// To see these outputs, run `azd env get-values`,  or
// `azd env get-values --output json` for json output.
// To generate your own `.env` file run `azd env get-values > .env`

/* -------------------------- Feature flags ------------------------------- */

@description('If true, use and setup authentication with Azure Entra ID')
output USE_AUTHENTICATION bool = useAuthentication

@description('If true, deploy Azure AI Search Service')
output USE_AI_SEARCH bool = useAiSearch

@description('If true, reuse existing Azure OpenAI Service')
output USE_EXISTING_AZURE_OPENAI bool = useExistingAzureOpenAi

@description('If true, reuse existing Azure AI Search Service')
output USE_EXISTING_AI_SEARCH bool = useExistingAiSearch

/* --------------------------- Apps Deployment ----------------------------- */

@description('Endpoint URL of the Frontend service')
output SERVICE_FRONTEND_URL string = app.outputs.frontendAppUrl

@description('Endpoint URL of the Backend service')
output SERVICE_BACKEND_URL string = app.outputs.backendAppUrl

@description('The endpoint of the container registry.') // necessary for azd deploy
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = app.outputs.containerRegistryLoginServer

/* ------------------------ Authentication & RBAC ------------------------- */

@description('ID of the tenant we are deploying to')
output AZURE_AUTH_TENANT_ID string = authTenantId

@description('Principal ID of the user running the deployment')
output AZURE_PRINCIPAL_ID string = azurePrincipalId

@description('Application registration client ID')
output AZURE_CLIENT_APP_ID string = authClientAppId

/* -------------------------- Azure AI Foundry ----------------------------- */

@description('Azure AI Project connection string')
output AZURE_AI_PROJECT_CONNECTION_STRING string = aiProject.outputs.connectionString

/* ---------------------------- Azure OpenAI ------------------------------- */

@description('Azure OpenAI service name')
output AZURE_OPENAI_NAME string = _azureOpenAiName

@description('Azure OpenAI endpoint - Base URL for API calls to Azure OpenAI')
output AZURE_OPENAI_ENDPOINT string = _azureOpenAiEndpoint

@description('Azure OpenAI API Version - API version to use when calling Azure OpenAI')
output AZURE_OPENAI_API_VERSION string = _azureOpenAiApiVersion

@description('Azure OpenAI Model Deployment Name - Executor Service')
output EXECUTOR_AZURE_OPENAI_DEPLOYMENT_NAME string = _executorAzureOpenAiDeploymentName

@description('Azure OpenAI Model Deployment Name - Utility Service')
output UTILITY_AZURE_OPENAI_DEPLOYMENT_NAME string = _utilityAzureOpenAiDeploymentName

@description('JSON deployment configuration for the models')
output AZURE_OPENAI_DEPLOYMENTS object[] = deployments

/* ------------------------------ AI Search --------------------------------- */

@description('Azure AI Search service name')
output AZURE_AI_SEARCH_NAME string = _azureAiSearchName

@description('Azure AI Search service resource group name')
output AZURE_AI_SEARCH_RESOURCE_GROUP_NAME string = azureAiSearchResourceGroupName

@description('Azure AI Search deployment location')
output AZURE_AI_SEARCH_LOCATION string = azureAiSearchLocation

@description('Azure AI Search endpoint SKU name')
output AZURE_AI_SEARCH_SKU_NAME string = aiSearchSkuName

@description('Azure OpenAI endpoint - Base URL for API calls to Azure OpenAI')
// This environment variable name is used as a default by Semantic Kernel
output AZURE_AI_SEARCH_ENDPOINT string = _azureAiSearchEndpoint

/* -------------------------- Diagnostic Settings --------------------------- */

@description('Application Insights name')
output AZURE_APPLICATION_INSIGHTS_NAME string = appInsightsComponent.outputs.name

@description('Log Analytics Workspace name')
output AZURE_LOG_ANALYTICS_WORKSPACE_NAME string = logAnalyticsWorkspace.outputs.name

@description('Application Insights connection string')
output APPLICATIONINSIGHTS_CONNECTION_STRING string = appInsightsComponent.outputs.connectionString

@description('Semantic Kernel Diagnostics')
output SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS bool = true

@description('Semantic Kernel Diagnostics: if set, content of the messages is traced. Set to false in production')
output SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS_SENSITIVE bool = true

/* --------------------------- AI Foundry ------------------------------ */
@description('Azure AI Foundry Hub name')
output AI_HUB_NAME string = hub.outputs.name

@description('Azure AI Foundry Project name')
output AI_PROJECT_NAME string = project.outputs.name

@description('Azure AI Foundry Project Connection string')
output AI_PROJECT_CONNECTION_STRING string = '${location}.api.azureml.ms;${last(split(subscription().id, '/'))};${resourceGroup().name};${project.outputs.name}'
