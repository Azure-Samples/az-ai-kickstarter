#!/usr/bin/env pwsh
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:DEBUG -match '^1|yes|true$') {
    Set-PSDebug -Trace 2
}

# Add here commands that need to be executed after deployment
# Typically: preparing additional environment variables, creating app registrations, etc.
# see https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/azd-extensibility
