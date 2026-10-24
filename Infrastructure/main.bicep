// Entry point. Deploys at subscription scope so the resource group name can be a parameter too.
// It creates the resource group and then deploys resources.bicep into it.
//
// Deploy:   az deployment sub create --name spec-guardrail --location <region> --parameters main.bicepparam
// Clean up: delete the resource group, then purge the soft-deleted Foundry account and API Management
//           instance (az cognitiveservices account purge, az apim deletedservice purge).

targetScope = 'subscription'

@description('Name of the resource group to create.')
param resourceGroupName string

@description('Azure region for the resource group and all resources. It must offer the model (gpt-6-luna with GlobalStandard was checked in swedencentral).')
param location string

@description('Short prefix for resource names.')
@minLength(3)
@maxLength(12)
param namePrefix string = 'specguard'

@description('GitHub user or organization whose workflows may sign in with OIDC.')
param githubOwner string

@description('GitHub repository whose pull_request workflows may sign in with OIDC.')
param githubRepo string

@description('Publisher email shown by API Management (required by the service).')
param publisherEmail string

@description('Publisher name shown by API Management.')
param publisherName string = 'spec-guardrail'

@description('Model to deploy. The deployment gets the same name, so clients send it as "model".')
param modelName string = 'gpt-6-luna'

@description('Model version.')
param modelVersion string = '2026-09-22'

@description('Deployment SKU.')
param modelSku string = 'GlobalStandard'

@description('Deployment capacity in units of 1000 tokens per minute.')
param modelCapacity int = 50

@description('Token limit per minute enforced by the gateway. Keep it at or below the deployment capacity.')
param tokensPerMinute int = 50000

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
}

module resources 'resources.bicep' = {
  scope: rg
  name: 'spec-guardrail-resources'
  params: {
    location: location
    namePrefix: namePrefix
    githubOwner: githubOwner
    githubRepo: githubRepo
    publisherEmail: publisherEmail
    publisherName: publisherName
    modelName: modelName
    modelVersion: modelVersion
    modelSku: modelSku
    modelCapacity: modelCapacity
    tokensPerMinute: tokensPerMinute
  }
}

// The names match the repository variables the workflow reads
output AZURE_CLIENT_ID string = resources.outputs.AZURE_CLIENT_ID
output AZURE_TENANT_ID string = resources.outputs.AZURE_TENANT_ID
output APIM_AUDIENCE string = resources.outputs.APIM_AUDIENCE
output APIM_ENDPOINT string = resources.outputs.APIM_ENDPOINT
output SPEC_GUARDRAIL_MODEL string = resources.outputs.SPEC_GUARDRAIL_MODEL
output resourceGroupName string = rg.name
output foundryName string = resources.outputs.foundryName
output apimName string = resources.outputs.apimName
