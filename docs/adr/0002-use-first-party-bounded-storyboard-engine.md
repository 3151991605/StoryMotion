# ADR-0002: Use a first-party bounded storyboard engine for the MVP

## Status

Accepted

## Context

The original design treated PenShot as the primary `ScreenplayPackage` to
`ShotPackage` implementation. PenShot 0.3.4 required experimental patches to
import, ignored its rule-mode setting, made unexpected model calls, produced no
fragments, and failed on LangGraph state serialization. Its StoryMotion adapter
and isolated sidecar contract remain valid, but its current workflow is not a
reliable MVP dependency.

StoryMotion's bounded `MiniMaxShotProvider` has now completed one real
MiniMax-M3 request and produced six strictly validated shots totaling 60
seconds.

## Decision

Use `MiniMaxShotProvider` as the primary MVP storyboard engine. Keep
`RuleShotProvider` as the deterministic fallback. Retain the PenShot adapter and
sidecar boundary as an optional future integration, but do not run or patch the
PenShot workflow in the product path.

The next product boundary is a first-party media provider layer. Image and
video providers receive StoryMotion-owned request models and return
StoryMotion-owned artifacts or tasks. Vendor response objects never cross into
graphs, services, APIs, or the frontend.

## Consequences

### Positive

- StoryMotion controls shot count, duration, IDs, references, retries, and cost.
- The storyboard path is testable without PenShot dependencies or side effects.
- PenShot can be revisited without changing upper layers.

### Negative

- StoryMotion owns prompt enrichment and continuity logic for the MVP.
- PenShot-specific features are unavailable until its runtime becomes stable.

### Risks and mitigations

- Model output truncation: bounded output budget and strict fail-closed parsing.
- Vendor outage: deterministic RuleShot fallback.
- Character drift: fixed character prompts plus image-to-video reference frames.
- Media cost: submit one shot at a time and never retry automatically.

## Evidence

- `outputs/verification/penshot_feasibility_summary.json`
- `outputs/verification/penshot_rule_workflow_summary.json`
- `outputs/verification/minimax_shot_provider_summary.json`
- `outputs/verification/minimax_shot_provider_package.json`
