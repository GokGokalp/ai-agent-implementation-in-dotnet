# Proposal

## Why

The product search agent has behavior that only exists in the agent prompt and in the search tool code. Nothing describes it as a contract, so a later change to it (for example the number of results) has no spec to be compared against. This baseline records what the system does today, so future changes can be expressed as deltas against it.

## What Changes

- Record the current product search behavior as a new `product-search` capability: keyword-based search, a bounded number of results, answers grounded in what the search returned, and price constraints applied in the summary.
- No code changes and no new behavior. The spec follows the code as it is today, not what the prompt promises beyond it.

## Capabilities

### New Capabilities
- `product-search`: How the agent searches the electronics catalog and presents the results to the user.

### Modified Capabilities

## Impact

- No application code is affected.
- Archiving this change creates `openspec/specs/product-search/spec.md`, the first main spec of the project.
