using Azure;
using Azure.Search.Documents;
using Azure.Search.Documents.Indexes;
using Azure.Search.Documents.Indexes.Models;
using Azure.Search.Documents.Models;

namespace ProductSearchAgent.Data;

public static class SearchIndexSeeder
{
    public static async Task SeedAsync(string endpoint, string apiKey, string indexName)
    {
        var credential = new AzureKeyCredential(apiKey);
        var indexClient = new SearchIndexClient(new Uri(endpoint), credential);
        var searchClient = new SearchClient(new Uri(endpoint), indexName, credential);

        await CreateIndexAsync(indexClient, indexName);
        await UploadProductsAsync(searchClient);

        Console.WriteLine("Seeding complete.");
    }

    private static async Task CreateIndexAsync(SearchIndexClient indexClient, string indexName)
    {
        var index = new SearchIndex(indexName)
        {
            Fields =
            [
                new SimpleField("id", SearchFieldDataType.String) { IsKey = true },
                new SearchableField("name"),
                new SearchableField("description"),
                new SearchableField("brand"),
                new SearchableField("category"),
                new SimpleField("price", SearchFieldDataType.Double),
                new SearchableField("specifications"),
            ]
        };

        await indexClient.CreateOrUpdateIndexAsync(index);
        Console.WriteLine($"Index '{indexName}' created or updated.");
    }

    private static async Task UploadProductsAsync(SearchClient searchClient)
    {
        var products = new[]
        {
            new SearchDocument
            {
                ["id"] = "1",
                ["name"] = "Dell XPS 15",
                ["brand"] = "Dell",
                ["category"] = "Laptop",
                ["price"] = 1499.99,
                ["description"] = "15.6-inch premium laptop with OLED display, ideal for professionals and creators.",
                ["specifications"] = "Intel Core i7-13700H, 16GB RAM, 512GB SSD, NVIDIA RTX 4060, 15.6\" OLED 3.5K"
            },
            new SearchDocument
            {
                ["id"] = "2",
                ["name"] = "Apple MacBook Pro 14",
                ["brand"] = "Apple",
                ["category"] = "Laptop",
                ["price"] = 1999.99,
                ["description"] = "Compact pro laptop powered by Apple M3 Pro chip with exceptional battery life.",
                ["specifications"] = "Apple M3 Pro, 18GB RAM, 512GB SSD, 14\" Liquid Retina XDR, 18h battery"
            },
            new SearchDocument
            {
                ["id"] = "3",
                ["name"] = "Lenovo ThinkPad X1 Carbon",
                ["brand"] = "Lenovo",
                ["category"] = "Laptop",
                ["price"] = 1349.00,
                ["description"] = "Ultra-light business laptop built for durability and long battery life.",
                ["specifications"] = "Intel Core i5-1335U, 16GB RAM, 256GB SSD, 14\" IPS FHD, 15h battery, 1.12kg"
            },
            new SearchDocument
            {
                ["id"] = "4",
                ["name"] = "ASUS ROG Strix G16",
                ["brand"] = "ASUS",
                ["category"] = "Gaming Laptop",
                ["price"] = 1799.00,
                ["description"] = "High-performance gaming laptop with fast refresh rate display and powerful GPU.",
                ["specifications"] = "Intel Core i9-13980HX, 32GB RAM, 1TB SSD, NVIDIA RTX 4070, 16\" QHD 240Hz"
            },
            new SearchDocument
            {
                ["id"] = "5",
                ["name"] = "Acer Aspire 5",
                ["brand"] = "Acer",
                ["category"] = "Laptop",
                ["price"] = 599.99,
                ["description"] = "Budget-friendly everyday laptop great for students and light work.",
                ["specifications"] = "AMD Ryzen 5 7530U, 8GB RAM, 512GB SSD, 15.6\" FHD IPS"
            }
        };

        var batch = IndexDocumentsBatch.Upload(products);
        await searchClient.IndexDocumentsAsync(batch);
        Console.WriteLine($"Uploaded {products.Length} products.");
    }
}
