using System.ComponentModel;
using Azure.Search.Documents;
using Azure.Search.Documents.Models;

namespace ProductSearchAgent.Tools;

public class ProductSearchTool
{
    private readonly SearchClient _searchClient;

    public ProductSearchTool(SearchClient searchClient)
    {
        _searchClient = searchClient;
    }

    [Description("Search the product catalog for electronics products. Returns matching products with name, description, price, and specifications. Use this when the user is looking for products.")]
    public async Task<string> SearchProducts(
        [Description("Plain keyword search terms from the user's request, e.g. 'laptop', 'gaming laptop', 'dell xps', 'macbook'.")] string query)
    {
        var options = new SearchOptions
        {
            Size = 5,
            Select = { "name", "description", "price", "category", "brand", "specifications" }
        };

        Console.WriteLine($"ProductSearchTool: SearchProducts called with query: \"{query}\"");
        var results = await _searchClient.SearchAsync<SearchDocument>(query, options);
        var products = new List<string>();

        await foreach (var result in results.Value.GetResultsAsync())
        {
            var doc = result.Document;
            string Get(string key) => doc.TryGetValue(key, out var v) ? v?.ToString() ?? "" : "";

            products.Add($"Product: {Get("name")} | Brand: {Get("brand")} | Category: {Get("category")} | Price: ${Get("price")} | Description: {Get("description")}");
        }

        if (products.Count == 0)
            return "No products found matching the search query.";

        var names = products
            .Select(p => p.Split('|')[0].Replace("Product: ", "").Trim())
            .ToList();
        Console.WriteLine($"ProductSearchTool: {products.Count} products found: {string.Join(", ", names)}");

        return string.Join("\n", products);
    }
}
