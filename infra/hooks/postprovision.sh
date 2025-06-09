#!/bin/bash

# Add here commands that need to be executed after provisioning
# Typically: loading data in databases, AI Search or storage accounts, etc.
# see https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/azd-extensibility


shopt -s nocasematch

if [[ "${USE_AUTHENTICATION-}" =~ "true" ]]; then
    printf "  \033[32m➜\033[0m Authentication is enabled updating login callback...\n"

    redirect_uri="$SERVICE_FRONTEND_URL/.auth/login/aad/callback"

    printf "    Adding app registration redirect URI '${redirect_uri}'...\n"
    az ad app update \
        --id "$AZURE_CLIENT_APP_ID" \
        --web-redirect-uris "http://localhost:5801/.auth/login/aad/callback" "$redirect_uri" \
        --output table

    # Remove the secret from the environment after it has been set in the keyvault
    azd env set AZURE_CLIENT_APP_SECRET ""
fi

if [[ "${USE_AI_SEARCH-}" =~ "true" ]]; then
    printf "  \033[32m➜\033[0m We are using Azure AI Search: ingesting example documents...\n"

    (
        cd src/ingestion
        uv run ingestor.py
    )
fi



