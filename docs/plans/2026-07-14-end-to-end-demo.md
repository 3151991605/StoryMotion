# End-to-End Demo Orchestration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build one repeatable local command that turns existing StoryMotion protocol artifacts into a validated cross-layer bundle and playable Mock MP4.

**Architecture:** A dependency-injected `DemoPipeline` owns orchestration and artifact persistence. A thin CLI loads the existing MiniMax JSON artifacts, finds workspace-local FFmpeg, invokes the pipeline, and emits a machine-readable summary.

**Tech Stack:** Python 3.11, Pydantic 2, pytest, FFmpeg

---

### Task 1: Define the orchestration contract with failing tests

**Files:**
- Create: `tests/test_demo_pipeline.py`
- Create: `src/storymotion/services/demo_pipeline.py`

**Step 1:** Add a test that loads `tests/fixtures/valid_storymotion_bundle.json`, passes its first three layers to `DemoPipeline`, and uses a recording video provider.

**Step 2:** Assert that the pipeline regenerates a valid storyboard, writes `storymotion_bundle.json`, calls the video provider exactly once, and returns paths under the requested output directory.

**Step 3:** Run `python -m pytest tests/test_demo_pipeline.py -v` and verify the import fails before implementation.

### Task 2: Implement the minimal DemoPipeline service

**Files:**
- Create: `src/storymotion/services/demo_pipeline.py`
- Modify: `src/storymotion/services/__init__.py`

**Step 1:** Define provider protocols for shot generation and video rendering.

**Step 2:** Define a small immutable result dataclass containing the validated bundle, bundle path, storyboard path, and video path.

**Step 3:** Implement `run()` to generate shots, validate `StoryMotionBundle`, write UTF-8 JSON with `ensure_ascii=False`, and invoke the injected video provider.

**Step 4:** Run the focused test and verify it passes.

### Task 3: Add the local end-to-end CLI

**Files:**
- Create: `scripts/run_end_to_end_demo.py`
- Create: `tests/test_end_to_end_demo_cli.py`

**Step 1:** Add focused tests for loading protocol files and locating FFmpeg without invoking external processes.

**Step 2:** Implement CLI defaults pointing to the verified ProjectBrief, StoryPackage, repaired ScreenplayPackage, and `outputs/verification/end_to_end_demo`.

**Step 3:** Print a JSON summary containing pass/fail, durations, shot count, and relative artifact paths; never print secrets.

**Step 4:** Run the focused CLI tests and verify they pass.

### Task 4: Execute the integration gate

**Files:**
- Create: `outputs/verification/end_to_end_demo/*`
- Create: `outputs/verification/end_to_end_demo_summary.json`

**Step 1:** Run the CLI with the workspace virtual environment.

**Step 2:** Verify the generated MP4 with workspace-local `ffprobe`: duration approximately 60 seconds, 720x1280, H.264 video, and AAC audio.

**Step 3:** Run `python -m pytest -q` and require the full suite to pass.

**Step 4:** Record whether the deterministic full chain is feasible and retain Hailuo status code 2056 as an external account-resource blocker rather than an architecture failure.

> Note: this workspace is not a Git repository, so the plan's usual per-task commit steps are not applicable.
