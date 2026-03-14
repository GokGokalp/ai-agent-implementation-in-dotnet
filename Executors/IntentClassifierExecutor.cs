using System.Text.Json;
using Microsoft.Agents.AI;
using Microsoft.Agents.AI.Workflows;
using Microsoft.Extensions.AI;
using ProductSearchAgent.Models;

namespace ProductSearchAgent.Executors;

public class IntentClassifierExecutor : Executor<ChatMessage, IntentResult>
{
    private readonly AIAgent _agent;

    public IntentClassifierExecutor(AIAgent agent) : base("IntentClassifierExecutor")
    {
        _agent = agent;
    }

    public override async ValueTask<IntentResult> HandleAsync(
        ChatMessage message, IWorkflowContext context, CancellationToken cancellationToken = default)
    {
        var response = await _agent.RunAsync(message, cancellationToken: cancellationToken);
        var result = JsonSerializer.Deserialize<IntentResult>(response.Text) ?? new IntentResult { Intent = "unknown" };
        result.OriginalQuery = message.Text ?? string.Empty;
        
        Console.WriteLine($"IntentClassifierExecutor: Routed to \"{result.Intent}\" | Query: \"{result.OriginalQuery}\"");
        return result;
    }
}
