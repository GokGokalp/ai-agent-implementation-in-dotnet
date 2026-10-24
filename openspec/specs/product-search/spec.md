# product-search Specification

## Purpose
Finds products in the electronics catalog and summarizes them for the user, using only what the search returned.

## Requirements

### Requirement: Keyword-based catalog search
The search agent SHALL search the catalog with the user's own keywords and SHALL NOT replace them with generic category names.

#### Scenario: Specific product keywords
- **WHEN** the user asks for "gaming laptop"
- **THEN** the catalog is searched with keywords such as "gaming laptop", not a generic term like "electronics"

### Requirement: Bounded search results
Each search SHALL return at most 5 products, each with name, brand, category, price and description.

#### Scenario: Many matching products
- **WHEN** more than 5 products match the keywords
- **THEN** only the top 5 results are returned to the agent

#### Scenario: No matching products
- **WHEN** no product matches the keywords
- **THEN** the search reports that no products were found

### Requirement: Grounded answers
The search agent SHALL present only products that the search returned and SHALL always mention their price. When the search finds nothing, it SHALL say so and suggest broadening the search.

#### Scenario: Presenting results
- **WHEN** the search returns products
- **THEN** the answer summarizes them with their price and does not include products that were not returned

#### Scenario: Empty results
- **WHEN** the search finds no products
- **THEN** the answer tells the user and suggests broadening the search

### Requirement: Price constraints in summaries
When the user states a price constraint, the search agent SHALL apply it when summarizing the results.

#### Scenario: Budget limit
- **WHEN** the user asks for a laptop under 1500
- **THEN** products above 1500 are left out of the summary
