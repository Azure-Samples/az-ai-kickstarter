# 5. Use Azure Container Registry image builds

Date: 2024-12-25

## Status

In review

## Context

Not everyone has a local _Docker_ environment. Through AZD we have two easy options in building container images: 
1. Local [Docker](https://www.docker.com/) build of the images
2. Remote [Azure Container Registry](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-tutorial-quick-task) build.

Some images can get quite big, building them online avoids a long wait while pushing the newly built image for the first time

## Decision

By default build the containers remotely to make things as simple as possible.
To build locally, just comment the line in `azure.yaml`:
```yaml
# see https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/azd-schema
name: az-ai-kickstarter
metadata:
  template: dbroeglin/generator-az-ai@0.0.10
services:
  backend:
    language: python
    project: src/backend
    host: containerapp
    docker:
      path: ./Dockerfile
#      remoteBuild: true
```


## Consequences

Build happens by default remotely. To get back to local building comment the line in `azure.yaml`