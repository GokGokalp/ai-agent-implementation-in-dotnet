# Design

## Context

The behavior lives in two places: the product search prompt (`Prompts/AgentPrompts.cs`) and the search tool (`Tools/ProductSearchTool.cs`). See proposal.md - Why. There are no tests and no existing specs.

## Goals / Non-Goals

**Goals:**
- Describe the observable behavior as it is today, so a later change can be written as a delta against it.
- Keep one cohesive capability, `product-search`, instead of splitting it by file.

**Non-Goals:**
- Intent routing and the HTTP endpoint. They are separate behavior and can get their own capabilities later.
- Fixing or improving anything the baseline reveals.

## Decisions

**The spec follows the code, not the prompt.** Where the prompt promises more than the code delivers, the spec only states what the code can deliver. The prompt asks the agent to mention "key specs", but the search tool does not return the specifications field to the agent, so the spec requires price and not specs. Alternative: spec what the prompt asks for. Rejected, because the spec would be wrong from day one and every later check would flag it.

**Observable behavior only.** Requirements talk about searches, results and answers, not about classes or the tool's name, so the implementation can change without changing the spec.

## Risks / Trade-offs

- [The price constraint is applied by the language model while summarizing, not by a hard filter, so it can be wrong] → The requirement states the behavior as it is. A hard filter on the search side would be a separate change with its own delta.
- [The prompt and the spec can drift apart, since the prompt is not generated from the spec] → Future changes to either should go through a delta, which is what this baseline enables.
