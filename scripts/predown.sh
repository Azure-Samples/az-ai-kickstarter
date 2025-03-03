#!/bin/bash
set -euo pipefail
[[ ${DEBUG-} =~ ^1|yes|true$ ]] && set -o xtrace

# Add here commands that need to be executed before provisioning
# Typically: preparing additional environment variables, creating app registrations, etc.
# see https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/azd-extensibility

if [[ "${USE_AUTHENTICATION-}" =~ "true" ]]; then
  printf "  \033[32m➜\033[0m Authentication was enabled deleting app registration...\n"

  AZURE_APP_ID=$(
    az ad app show \
      --id "${AZURE_CLIENT_APP_ID:-00000000-0000-0000-0000-000000000000}" \
      --query id \
      -o tsv 2> /dev/null || true)

  if [ ! -z "$AZURE_APP_ID" ]; then
    echo "Deleting app $AZURE_CLIENT_APP_ID..."
    az ad app delete --id "$AZURE_APP_ID"
  fi
fi

