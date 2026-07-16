# Anthropic Writer feasibility probe

## Goal

Verify the final Writer node without regenerating the already validated worldview,
character, and plot nodes.

## Chosen approach

Add a separate probe for the MiniMax Anthropic-compatible endpoint. The probe uses
`MiniMax-M2.7`, a 4096-token output limit, and a compact context containing only
facts needed to write the draft. It performs exactly one generation request.

The existing MiniMax-M3/OpenAI graph remains unchanged so its failure evidence is
preserved. On success, the new probe validates `StoryDraft` with Pydantic, assembles
the canonical `StoryPackage` locally, and saves both the final package and a run
summary. On failure, it saves returned text and diagnostic metadata.

## Alternatives considered

- Retry M3 with a shorter prompt: rejected for this probe because the previous run
  spent the entire 2048-token completion allowance on reasoning.
- Regenerate the whole graph with M2.7: rejected because it would waste text quota
  and blur the Writer-specific result.
- Disable reasoning: not selected because the current official MiniMax compatibility
  documentation does not provide a reliable supported switch for this model path.

## Verification

Unit tests cover payload shape, compact context, response block extraction, and
strict draft validation. The live result passes only when a 500-650 character draft
is returned and a complete `StoryPackage` can be assembled from cached inputs.
