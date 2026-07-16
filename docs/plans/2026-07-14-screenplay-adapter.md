# Screenplay Adapter Feasibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert the validated `StoryPackage` into a strictly validated, 60-second `ScreenplayPackage` with one MiniMax-M2.7 request.

**Architecture:** The model returns only a bounded `ScenePackage`; deterministic local code injects the canonical title, character definitions, and location definitions from `StoryPackage`. This prevents cross-layer definition drift and reduces output tokens. The live probe uses the MiniMax Anthropic-compatible endpoint and persists success or failure evidence.

**Tech Stack:** Python 3.11, Pydantic v2, urllib, pytest, MiniMax Anthropic-compatible API.

---

### Task 1: Add the bounded scene protocol

**Files:**
- Modify: `src/storymotion/models/intermediate.py`
- Modify: `src/storymotion/models/__init__.py`
- Test: `tests/test_screenplay_assembly.py`

**Step 1: Write the failing test**

Create a `ScenePackage` containing scenes and verify duplicate scene IDs and total duration are rejected.

**Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest tests/test_screenplay_assembly.py -q`

Expected: FAIL because `ScenePackage` does not exist.

**Step 3: Write minimal implementation**

Add a strict `ScenePackage` model with `target_duration` and `scenes`. Validate unique scene IDs and require scene durations to sum to `target_duration`.

**Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest tests/test_screenplay_assembly.py -q`

Expected: PASS.

### Task 2: Add deterministic screenplay assembly

**Files:**
- Create: `src/storymotion/services/screenplay_assembler.py`
- Modify: `src/storymotion/services/__init__.py`
- Test: `tests/test_screenplay_assembly.py`

**Step 1: Write the failing test**

Call `assemble_screenplay_package(story, scene_package)` and assert that title, characters, locations, and duration exactly match the story layer.

**Step 2: Run test to verify it fails**

Expected: FAIL because the assembler does not exist.

**Step 3: Write minimal implementation**

Construct `ScreenplayPackage` using canonical definitions from `StoryPackage` and scenes from `ScenePackage`. Reject duration mismatches through the strict models.

**Step 4: Run test to verify it passes**

Expected: PASS.

### Task 3: Add the one-request live probe

**Files:**
- Create: `scripts/verify_minimax_screenplay_adapter.py`
- Create: `tests/test_minimax_screenplay_probe.py`

**Step 1: Write failing probe tests**

Verify the payload uses `MiniMax-M2.7`, Anthropic `max_tokens`, scene-only output, compact story context, and text-block extraction.

**Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest tests/test_minimax_screenplay_probe.py -q`

Expected: FAIL because the probe does not exist.

**Step 3: Implement the probe**

Load the existing `story_package.json`, request 3-5 scenes totaling 60 seconds, validate `ScenePackage`, assemble `ScreenplayPackage`, and write a summary plus raw failure evidence when needed.

**Step 4: Run the full test suite**

Run: `.venv/Scripts/python.exe -m pytest -q`

Expected: all tests PASS.

### Task 4: Run and assess the feasibility probe

**Files:**
- Create on success: `outputs/verification/screenplay/screenplay_package.json`
- Create: `outputs/verification/minimax_m27_screenplay_summary.json`

**Step 1: Make one live request**

Run: `.venv/Scripts/python.exe scripts/verify_minimax_screenplay_adapter.py --max-tokens 4096 --timeout 180`

Expected: one request only; cached `StoryPackage` is not regenerated.

**Step 2: Verify the artifact locally**

Check scene count, unique IDs, valid character/location references, dialogue speakers, and exact 60-second total duration.

**Step 3: Record the conclusion**

Mark the phase Go only if strict Pydantic validation and deterministic assembly both succeed. Git commit steps are omitted because this workspace is not a valid Git repository.
