#!/bin/bash
set -euo pipefail
[[ ${DEBUG-} =~ ^1|yes|true$ ]] && set -o xtrace

# Add here commands that need to be executed before provisioning
# Typically: preparing additional environment variables, creating app registrations, etc.
# see https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/azd-extensibility

if [[ "${USE_AUTHENTICATION-}" =~ "true" ]]; then
    printf "  \033[32m➜\033[0m Authentication is enabled creating app registration...\n"

    if [ -z "${AZURE_AUTH_TENANT_ID-}" ]; then
        AZURE_AUTH_TENANT_ID=$(az account show --query tenantId -o tsv)
        printf "      \033[3;33mAZURE_AUTH_TENANT_ID not provided: Default to $AZURE_AUTH_TENANT_ID from AZ CLI\033[0m"
    fi
    azd env set AZURE_AUTH_TENANT_ID "$AZURE_AUTH_TENANT_ID"

    app_name="$AZURE_ENV_NAME-app"
    current_user_upn=$(az ad signed-in-user show --query userPrincipalName -o tsv)
    current_user_id=$(az ad user show --id "$current_user_upn" --query id --output tsv)
    AZURE_CLIENT_APP_ID=$(az ad app list --display-name "${app_name}" --query '[].appId' -o tsv)

    printf "      Current user          : $current_user_upn"
    printf "      Current tenant        : $AZURE_AUTH_TENANT_ID"
    printf "      App Registration name : $app_name"

    if [ -z "$AZURE_CLIENT_APP_ID" ];
    then
        printf "    Creating app $app_name..."
        azure_app_object_id=$(
            az ad app create \
                --display-name "$app_name" \
                --web-redirect-uris http://localhost:5801/ \
                --query id \
                --output tsv
        )
        AZURE_CLIENT_APP_ID=$(
            az ad app show --id $azure_app_object_id --query appId -o tsv
        )

        az ad app update \
            --id $AZURE_CLIENT_APP_ID \
            --identifier-uris "api://$AZURE_CLIENT_APP_ID" \
            --enable-id-token-issuance true \
            --enable-access-token-issuance true \
            --required-resource-accesses @scripts/requiredResourceAccess.json

        SERVICE_PRINCIPAL_ID=$(
            az ad sp create \
                --id "$AZURE_CLIENT_APP_ID" \
                --query id \
                --output tsv
        )

        az ad app owner add \
            --id "$AZURE_CLIENT_APP_ID" \
            --owner-object-id "$current_user_id"

        AZURE_CLIENT_APP_SECRET="$(
            az ad app credential reset \
                --id $AZURE_CLIENT_APP_ID \
                --display-name "client-secret" \
                --query password \
                --years 1 \
                --output tsv
        )"

        az rest \
            --method PATCH \
            --headers 'Content-Type=application/json' \
            --uri "https://graph.microsoft.com/v1.0/applications/$azure_app_object_id" \
            --body @scripts/oauth2PermissionScopes.json

        az rest \
            --method PATCH \
            --headers 'Content-Type=application/json' \
            --uri "https://graph.microsoft.com/v1.0/applications/$azure_app_object_id" \
            --body @scripts/preAuthorizedApplications.json

        azd env set AZURE_CLIENT_APP_SECRET "$AZURE_CLIENT_APP_SECRET"

        printf "      App $app_name created with ID $AZURE_CLIENT_APP_ID and SP ID $SERVICE_PRINCIPAL_ID"
    else
        printf "      \033[3;33mApp '$AZURE_CLIENT_APP_ID' already exists, skipping creation\033[0m"
    fi

    azd env set AZURE_CLIENT_APP_ID "$AZURE_CLIENT_APP_ID"

    printf "    \033[32m➜\033[0m Application registration ${app_name} (${AZURE_CLIENT_APP_ID}) done.\n"

    # Credits: inspired by https://gpiskas.com/posts/automate-creation-app-registration-azure-cli/#creating-and-modifying-the-app-registration
fi

