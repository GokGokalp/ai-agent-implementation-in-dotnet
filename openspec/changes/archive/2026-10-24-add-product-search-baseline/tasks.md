# Tasks

## 1. Verify the baseline against the code

- [x] 1.1 Verify keyword-based search: confirm the product search prompt in `Prompts/AgentPrompts.cs` tells the agent to use the user's own keywords and not generic category names
- [x] 1.2 Verify bounded results: confirm `Tools/ProductSearchTool.cs` sets `Size = 5`, that each result line holds name, brand, category, price and description, and that zero results return "No products found matching the search query."
- [x] 1.3 Verify grounded answers: confirm the prompt forbids made-up products, asks for the price, and asks to suggest broadening the search when nothing is found
- [x] 1.4 Verify price constraints: confirm the prompt tells the agent to filter by the stated price range when summarizing
- [x] 1.5 Verify the spec does not promise more than the code: confirm no requirement mentions product specifications, since the search tool does not return them

## 2. Validate the change

- [x] 2.1 Run `openspec validate add-product-search-baseline` and verify it passes

## Workflow follow-up

- Archive the change after review so the main spec `openspec/specs/product-search/spec.md` is created.
- Verify the archived result.
