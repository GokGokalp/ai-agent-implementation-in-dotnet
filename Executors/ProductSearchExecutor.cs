using Microsoft.Agents.AI;
using Microsoft.Agents.AI.Workflows;
using ProductSearchAgent.Models;

namespace ProductSearchAgent.Executors;
public class ProductSearchExecutor : Executor<IntentResult, SearchAgentResponse>
{
    private readonly AIAgent _agent;

    public ProductSearchExecutor(AIAgent agent) : base("ProductSearchExecutor")
    {
        _agent = agent;
    }

    public override async ValueTask<SearchAgentResponse> HandleAsync(
        IntentResult message, IWorkflowContext context, CancellationToken cancellationToken = default)
    {
        var response = await _agent.RunAsync(message.OriginalQuery, cancellationToken: cancellationToken);
        Console.WriteLine($"ProductSearchExecutor: Final answer: {response.Text}");

        return new SearchAgentResponse
        {
            Answer = response.Text,
            Route = "search"
        };
    }
}