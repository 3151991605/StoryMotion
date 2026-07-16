# Bounded MiniMax Shot Provider Design

## Objective

Replace the unstable PenShot execution path with a first-party StoryMotion
provider that uses MiniMax M3 only for bounded creative enrichment. StoryMotion
continues to own shot count, IDs, scene references, character references,
durations, ordering, validation, and fallback behavior.

## Architecture

`MiniMaxShotProvider` first asks `RuleShotProvider` for a deterministic shot
skeleton. It sends the screenplay context and immutable shot IDs to MiniMax in
one chat-completions request. The model returns only creative fields: shot type,
camera movement, visual description, image prompt, video prompt, negative
prompt, and audio prompt.

The response is treated as untrusted input. StoryMotion removes an optional
reasoning block, extracts one JSON object, validates it with strict Pydantic
models, and requires exactly one enrichment for every expected shot ID. Model
ordering is ignored. Unknown, missing, or duplicate IDs, truncated output,
invalid JSON, transport errors, and schema errors become a classified
`MiniMaxShotProviderError`.

Final `Shot` objects always take `shot_id`, `scene_id`, `duration`, and
`character_ids` from the deterministic skeleton. This makes duration and
referential correctness independent of model behavior. There are no automatic
model retries. A generic `FallbackShotProvider` catches only explicitly
configured expected provider failures and delegates to `RuleShotProvider`.

## Transport and Safety

The default transport uses the MiniMax OpenAI-compatible
`/v1/chat/completions` endpoint with finite timeouts and a 2 MB response limit.
The API key is carried only in the Authorization header and never included in
raised error messages or verification artifacts. The transport is injectable,
so all structural and failure-path tests run without network access.

## Validation Strategy

Unit tests prove that there is exactly one transport call, immutable structural
fields cannot be changed by the model, out-of-order enrichments are restored to
canonical order, malformed output fails closed, and fallback does not hide
unrelated programming errors. After all offline and regression tests pass, one
real MiniMax M3 call is allowed with no retry. Its artifact records only model,
status, finish reason, token usage, shot counts, and validation results.

The first real probe showed that 4096 completion tokens were insufficient for
M3 reasoning plus six shot enrichments (`finish_reason=length`). The configured
default is therefore 8192 for the next explicitly authorized probe; the
single-request and no-retry constraints remain unchanged.

## Scope Boundary

This phase does not call Hailuo, generate final video, add a job queue, expose a
public API, or build UI. It establishes the reliable storyboard-generation
boundary that those later layers can consume.
