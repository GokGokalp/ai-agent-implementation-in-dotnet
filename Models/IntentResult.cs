using System.Text.Json.Serialization;

namespace ProductSearchAgent.Models;

public sealed class IntentResult
{
    [JsonPropertyName("intent")]
    public string Intent { get; set; } = string.Empty;

    [JsonIgnore]
    public string OriginalQuery { get; set; } = string.Empty;
}
