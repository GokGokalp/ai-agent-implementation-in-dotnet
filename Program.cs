using Azure;
using Azure.AI.OpenAI;
using Azure.Search.Documents;
using Microsoft.Agents.AI;
using Microsoft.Agents.AI.Workflows;
using Microsoft.Extensions.AI;
using ProductSearchAgent.Executors;
using ProductSearchAgent.Models;
using ProductSearchAgent.Prompts;
using ProductSearchAgent.Tools;

var builder = WebApplication.CreateBuilder(args);

// Azure OpenAI configuration
var azureOpenAiEndpoint = builder.Configuration["AzureOpenAI:Endpoint"]!;
var chatDeployment = builder.Configuration["AzureOpenAI:ChatDeployment"]!;
var azureOpenAiKey = builder.Configuration["AzureOpenAI:ApiKey"];

// Azure AI Search configuration
var searchEndpoint = builder.Configuration["AzureAISearch:Endpoint"]!;
var searchKey = builder.Configuration["AzureAISearch:ApiKey"]!;
var searchIndex = builder.Configuration["AzureAISearch:IndexName"]!;

// await SearchIndexSeeder.SeedAsync(searchEndpoint, searchKey, searchIndex);
// return;

// Create OpenAI chat client
var openAiClient = new AzureOpenAIClient(new Uri(azureOpenAiEndpoint), new AzureKeyCredential(azureOpenAiKey!));

// Middleware intercepts the LLM's tool-call decision
var chatClient = openAiClient.GetChatClient(chatDeployment)
    .AsIChatClient()
    .AsBuilder()
    .Use(inner => new AgentLoggingMiddleware(inner))
    .Build();

// Create the search tool
var searchClient = new SearchClient(new Uri(searchEndpoint), searchIndex, new AzureKeyCredential(searchKey));
var searchTool = new ProductSearchTool(searchClient);

// Create agents with their prompts and tools
AIAgent classifierAgent = new ChatClientAgent(chatClient, new ChatClientAgentOptions
{
    ChatOptions = new()
    {
        Instructions = AgentPrompts.IntentClassifier,
        ResponseFormat = ChatResponseFormat.ForJsonSchema<IntentResult>()
    }
});

AIAgent searchAgent = new ChatClientAgent(chatClient, new ChatClientAgentOptions
{
    ChatOptions = new()
    {
        Instructions = AgentPrompts.ProductSearch,
        Tools = [AIFunctionFactory.Create(searchTool.SearchProducts)]
    }
});

// Create executors for each agent
var classifierExecutor = new IntentClassifierExecutor(classifierAgent);
var searchExecutor = new ProductSearchExecutor(searchAgent);

// Build the workflow: classifier routes to search
var workflow = new WorkflowBuilder(classifierExecutor)
    .AddEdge<IntentResult>(classifierExecutor, searchExecutor,
        condition: result => result is not null && result.Intent == "search")
    .WithOutputFrom(searchExecutor)
    .Build();

var app = builder.Build();

app.MapGet("/api/search", async ([AsParameters] UserQuery request) =>
{
    await using var run = await InProcessExecution.RunStreamingAsync(
        workflow,
        new ChatMessage(ChatRole.User, request.Query));

    await run.TrySendMessageAsync(new TurnToken(emitEvents: true));

    SearchAgentResponse? response = null;
    await foreach (var evt in run.WatchStreamAsync())
    {
        if (evt is WorkflowOutputEvent outputEvent && outputEvent.Is<SearchAgentResponse>(out var agentResponse))
            response = agentResponse;
    }

    return response;
});

app.Run();
