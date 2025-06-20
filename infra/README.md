# Infrastructure as Code documentation

## Deploy with authentication enabled

> [!WARNING] 
> The account executing `azd` needs to be able to create Application Registrations in your Azure Entra ID tenant.

AZD can automatically configure authentication to secure the frontend and/or backend. To do so execute the following command before `azd up`:
```bash
azd env set USE_AUTHENTICATION true
```

If you already executed `azd up` just set the variable and run provisioning again:
```bash
azd env set USE_AUTHENTICATION true
azd provision
```

## Reusing existing resources

### Reusing an existing Azure OpenAI Service

```bash
azd env new _new_environment_name_
azd env set USE_EXISTING_AI_FOUNDRY True # Set to true to re-use existing Azure OpenAI
azd env set AZURE_OPENAI_NAME _existing_azure_openai_name_
azd env set AZURE_OPENAI_ENDPOINT _existing_azure_openai_endpoint_
azd env set AZURE_OPENAI_API_VERSION _existing_azure_openai_api_version_
azd env set EXECUTOR_AZURE_OPENAI_DEPLOYMENT_NAME _existing_executor_model_deployment_name_
azd env set UTILITY_AZURE_OPENAI_DEPLOYMENT_NAME _existing_utility_model_deployment_name_

# If your Azure AI Search Service is in another resource group:
azd env set AZURE_OPENAI_RESOURCE_GROUP_NAME _existing_ai_search_resource_group_name_
```

Note that `EXECUTOR_AZURE_OPENAI_DEPLOYMENT_NAME` and `UTILITY_AZURE_OPENAI_DEPLOYMENT_NAME` can be identical.

### Reusing an existing Azure AI Search Service

> [!CAUTION]
> Make sure you add the "Cognitive Services OpenAI User" role is assigned to the 
> User Assigned managed identity created for this deployment.


```bash
azd env new _your_environment_name_
azd env set USE_AI_SEARCH True            # Set to true to enable using AI Search 
azd env set USE_EXISTING_AI_SEARCH True   # Set to true to re-use existing AI Search
azd env set AZURE_AI_SEARCH_NAME _existing_ai_search_name_

# If your Azure AI Search Service is in another resource group:
azd env set AZURE_AI_SEARCH_RESOURCE_GROUP_NAME _existing_ai_search_resource_group_name_
```
