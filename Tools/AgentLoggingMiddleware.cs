using Microsoft.Extensions.AI;

namespace ProductSearchAgent.Tools;

public class AgentLoggingMiddleware(IChatClient inner) : DelegatingChatClient(inner)
{
    public override async Task<ChatResponse> GetResponseAsync(
        IEnumerable<ChatMessage> messages, ChatOptions? options = null, CancellationToken cancellationToken = default)
    {
        var response = await base.GetResponseAsync(messages, options, cancellationToken);

        foreach (var msg in response.Messages)
            foreach (var call in msg.Contents.OfType<FunctionCallContent>())
            {
                var args = call.Arguments?.Select(a => $"{a.Key}: {a.Value}") ?? [];
                Console.WriteLine($"AgentLoggingMiddleware: LLM decided to call {call.Name}({string.Join(", ", args)})");
            }

        return response;
    }
}