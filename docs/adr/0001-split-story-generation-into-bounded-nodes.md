# ADR-0001: Split story generation into bounded nodes

## Status
Accepted

## Context
The canonical `ProjectBrief` is stable across MiniMax-M3 calls, but a single request for a complete `StoryPackage` failed twice: first at a 60-second client timeout, then with `finish_reason=length`. In the second run, 2047 of 2048 completion tokens were consumed by reasoning and no JSON object was produced.

The MVP must remain observable, testable, and compatible with the MiniMax OpenAI-compatible endpoint while producing a 500–1000 character story.

## Decision
Generate a `StoryPackage` through four bounded sequential nodes:

1. World Builder returns only `Worldview`.
2. Character Agent returns only `CharacterPackage`.
3. Plot Planner returns only `PlotPlan`.
4. Writer returns only `StoryDraft`.

Python passes validated state between nodes and deterministically assembles the final `StoryPackage`. A node failure stops the run; the feasibility probe performs no automatic retry.

## Consequences

### Positive
- Each response fits a smaller output budget.
- Failures are attributable to a specific node.
- Validated intermediate outputs can be cached and retried independently.
- The implementation demonstrates real role separation without autonomous-agent unpredictability.

### Negative
- A successful story requires up to four model requests.
- Sequential latency and Token Plan usage increase.
- Prompt and schema versions must be kept aligned for four nodes.

### Neutral
- LangGraph is not required for this feasibility probe; the same nodes can be moved into LangGraph after their contracts are proven.

## Alternatives Considered

**One request for the complete StoryPackage**
- Rejected after measured timeout and completion-token truncation.

**Switch immediately to another API protocol with a larger output budget**
- Deferred because it would change both protocol and architecture, obscuring whether decomposition itself solves the measured problem.

**Generate only story text and hard-code all structured metadata**
- Rejected because it would not verify the proposed multi-agent data flow.

## References
- `outputs/verification/minimax_m3_story_package_summary.json`
- `outputs/verification/minimax_m3_story_package_failure.txt`
- `方案确定.md`

