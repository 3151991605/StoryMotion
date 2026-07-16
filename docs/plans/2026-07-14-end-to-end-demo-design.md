# End-to-End Demo Orchestration Design

## Goal

Turn the verified StoryMotion components into one repeatable local demo run that
accepts the existing `ProjectBrief`, `StoryPackage`, and `ScreenplayPackage`
artifacts and produces a validated `StoryMotionBundle` plus a playable Mock MP4.

## Chosen approach

Add a small application service rather than coupling the command-line entry point
directly to providers. `DemoPipeline` receives a shot provider and a video provider
through constructor injection. A run generates a `ShotPackage`, constructs a
`StoryMotionBundle` so all cross-layer invariants are checked, writes canonical
JSON artifacts, and asks the video provider to render the MP4.

The CLI is responsible only for loading UTF-8 JSON, locating the workspace-local
FFmpeg executable, choosing output paths, invoking the service, and printing a
sanitized summary. It will use the already generated MiniMax story and screenplay
artifacts, so this phase consumes no model tokens and does not depend on Hailuo
credits.

## Alternatives considered

1. Build Streamlit immediately. This gives a visible interface sooner, but would
   make UI state responsible for orchestration before the application boundary is
   stable.
2. Build FastAPI first. This is suitable for the final architecture, but adds HTTP
   schemas and server lifecycle work that do not improve the current feasibility
   proof.
3. Shell together the existing verification scripts. This is quick but brittle,
   difficult to test, and leaves no reusable application service for the future UI.

## Data flow

`ProjectBrief + StoryPackage + ScreenplayPackage` -> `RuleShotProvider` ->
`ShotPackage` -> `StoryMotionBundle` validation -> JSON artifacts ->
`MockVideoProvider` -> MP4 -> run summary.

## Failure handling

Protocol drift fails before rendering through Pydantic bundle validation. Missing
input files or FFmpeg fail with explicit paths. Provider failures propagate with
their original cause; the CLI exits non-zero and does not report a successful run.
No automatic retry is used because the local providers are deterministic.

## Verification

Unit tests use a recording video provider and the canonical fixture to prove call
order, cross-layer validation, and artifact creation without invoking FFmpeg. A
live local CLI check then uses the existing MiniMax artifacts and the workspace
FFmpeg runtime to create a real vertical MP4. Finally, the complete pytest suite
guards all earlier feasibility work.
