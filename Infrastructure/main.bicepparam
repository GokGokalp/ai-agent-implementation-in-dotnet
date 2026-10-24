using './main.bicep'

param resourceGroupName = 'rg-spec-guardrail'
param location = 'swedencentral'

param githubOwner = 'GokGokalp'
param githubRepo = 'ai-agent-implementation-in-dotnet'

// Replace before deploying. API Management requires a publisher email.
param publisherEmail = 'your_email@yahoo.com'
