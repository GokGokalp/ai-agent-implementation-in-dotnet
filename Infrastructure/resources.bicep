// Everything inside the resource group (called by main.bicep, which creates the group):
//   GitHub Actions (OIDC) -> API Management (AI gateway) -> Microsoft Foundry (model)
// No API keys anywhere.

targetScope = 'resourceGroup'

@description('Azure region. It must offer the model deployment below.')
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

var unique = uniqueString(resourceGroup().id)
var foundryName = '${namePrefix}-foundry-${unique}'
var apimName = '${namePrefix}-apim-${unique}'
var identityName = '${namePrefix}-github-oidc'

// Callers get tokens for this audience. A managed identity can only request tokens for a resource that
// is registered in the tenant, and this one always is. The gateway pins the caller's client id (see the policy).
var gatewayAudience = 'https://cognitiveservices.azure.com'

// Cognitive Services OpenAI User
var openAiUserRoleId = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

// ---------------------------------------------------------------------------
// Microsoft Foundry: resource, project and the model deployment
// ---------------------------------------------------------------------------

resource foundry 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: foundryName
    disableLocalAuth: true // Microsoft Entra only, API keys are switched off
    publicNetworkAccess: 'Enabled'
  }
}

resource project 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundry
  name: '${namePrefix}-project'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {}
}

resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: foundry
  name: modelName
  sku: {
    name: modelSku
    capacity: modelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: modelName
      version: modelVersion
    }
  }
  dependsOn: [
    project // changes on one account are applied one after another
  ]
}

// ---------------------------------------------------------------------------
// Federated identity for GitHub Actions
// ---------------------------------------------------------------------------

resource githubIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: identityName
  location: location
}

resource githubFederation 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: githubIdentity
  name: 'github-pull-request'
  properties: {
    issuer: 'https://token.actions.githubusercontent.com'
    subject: 'repo:${githubOwner}/${githubRepo}:pull_request'
    audiences: [
      'api://AzureADTokenExchange'
    ]
  }
}

// ---------------------------------------------------------------------------
// API Management as the AI gateway
// ---------------------------------------------------------------------------

resource apim 'Microsoft.ApiManagement/service@2024-05-01' = {
  name: apimName
  location: location
  sku: {
    name: 'Developer' // the llm-token-limit policy is not available in the Consumption tier
    capacity: 1
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
  }
}

// Only the gateway can call the model. The GitHub identity gets no role on Foundry.
resource gatewayToFoundry 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: foundry
  name: guid(foundry.id, apim.id, openAiUserRoleId)
  properties: {
    principalId: apim.identity.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', openAiUserRoleId)
  }
}

resource api 'Microsoft.ApiManagement/service/apis@2024-05-01' = {
  parent: apim
  name: 'foundry-openai-v1'
  properties: {
    displayName: 'Foundry (OpenAI v1)'
    path: 'openai/v1'
    protocols: [
      'https'
    ]
    subscriptionRequired: false // callers authenticate with a Microsoft Entra token, not a subscription key
    serviceUrl: 'https://${foundryName}.openai.azure.com/openai/v1'
  }
}

// One wildcard operation passes chat completions, responses and any other POST through to Foundry.
resource postAnyPath 'Microsoft.ApiManagement/service/apis/operations@2024-05-01' = {
  parent: api
  name: 'post-any-path'
  properties: {
    displayName: 'POST (any path)'
    method: 'POST'
    urlTemplate: '/*'
  }
}

resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2024-05-01' = {
  parent: api
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: replace(replace(replace(loadTextContent('policies/foundry-api.xml'), '__TENANT_ID__', tenant().tenantId), '__CLIENT_ID__', githubIdentity.properties.clientId), '__TOKENS_PER_MINUTE__', string(tokensPerMinute))
  }
  dependsOn: [
    postAnyPath
  ]
}

// ---------------------------------------------------------------------------
// Outputs: the names match the repository variables the workflow reads
// ---------------------------------------------------------------------------

output AZURE_CLIENT_ID string = githubIdentity.properties.clientId
output AZURE_TENANT_ID string = tenant().tenantId
output APIM_AUDIENCE string = gatewayAudience
output APIM_ENDPOINT string = '${apim.properties.gatewayUrl}/openai/v1'
output SPEC_GUARDRAIL_MODEL string = modelName
output foundryName string = foundry.name
output apimName string = apim.name
