# Streamlit Demo Interface Design

## Purpose and audience

The interface is a course-demo control room for StoryMotion. It lets reviewers
understand the complete pipeline in under two minutes: what the user supplied,
which AI stages produced which artifacts, what is genuinely validated, and why
the final video is currently a deterministic Mock rather than a Hailuo render.

## Chosen interaction model

Use one editorial dashboard instead of a multipage wizard. The left sidebar holds
the verified creative brief, demo-mode explanation, and artifact health. The main
canvas opens with a cinematic project header and four stage cards, followed by
tabs for story, screenplay, storyboard, and final video. This preserves context
during a live presentation and avoids rerun-driven navigation surprises.

The current brief is displayed as a verified offline case. A second "new idea"
mode is visibly marked as unavailable until live story generation is productized;
the UI must never imply that arbitrary edits generated the cached artifacts.

## Visual direction

The aesthetic is an oriental-fantasy production console: ink-black and deep navy
surfaces, aged-gold success accents, cinnabar warnings, hairline borders, and a
subtle radial glow behind the hero. Chinese display copy uses Song/Kai-style local
fonts while dense operational text uses Microsoft YaHei. The memorable motif is a
horizontal production rail connecting Story, Screenplay, Storyboard, and Media.

## Architecture and data flow

`src/storymotion/ui/demo_view_model.py` loads and validates the existing bundle and
verification summary into a framework-independent view model. `streamlit_app.py`
only renders that view model and reads the MP4 bytes. This keeps Streamlit out of
domain tests and allows a later FastAPI or React surface to reuse the same status
logic.

## Error handling and truthfulness

Missing or invalid artifacts produce an explicit blocking panel with the exact
local path and recovery command. Hailuo status code 2056 is shown as an external
quota warning, while all validated local stages remain green. No API keys are
loaded or displayed by the UI.

## Verification

Unit tests cover bundle/summary loading, stage status, shot rows, and missing-file
failure. The app is then launched locally using the project virtual environment,
opened in the in-app browser, and visually checked at desktop width. Finally the
full pytest suite is required to pass.
