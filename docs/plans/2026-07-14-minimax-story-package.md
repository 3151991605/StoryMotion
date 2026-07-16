# MiniMax StoryPackage Feasibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Verify with one MiniMax-M3 request that a validated ProjectBrief can produce a complete canonical StoryPackage.

**Architecture:** Load the previously validated ProjectBrief from disk, place its JSON in a compact generation prompt, then validate the response with the canonical `StoryPackage`. Apply a second cross-input check for protagonist, duration, character limit, and location limit.

**Tech Stack:** Python 3.11, standard-library HTTP client, Pydantic 2, pytest.

---

### Task 1: Add failing contract tests

**Files:**
- Create: `tests/test_minimax_story_probe.py`
- Modify: `tests/test_data_protocols.py`

**Steps:**
1. Require StoryPackage plot beats in the five-stage canonical order.
2. Test StoryPackage-to-ProjectBrief cross-input validation.
3. Test the prompt contains compact output and story length requirements.
4. Run focused tests and verify the missing probe fails collection.

### Task 2: Tighten the StoryPackage contract

**Files:**
- Modify: `src/storymotion/models/story.py`

**Steps:**
1. Reject missing, repeated, or reordered plot beat types.
2. Run protocol regression tests.

### Task 3: Implement the single-request probe

**Files:**
- Create: `scripts/verify_minimax_story_package.py`

**Steps:**
1. Load and validate the first successful ProjectBrief artifact.
2. Request exactly two characters, one location, five timed beats, and 500–650 Chinese characters of story text.
3. Set the documented OpenAI-compatible completion limit to 2048.
4. Validate the output and its relationship to the input brief.
5. Save validated output, latency, finish reason, model, and usage.
6. Do not retry failures automatically.

### Task 4: Execute the feasibility gate

**Files:**
- Generate: `outputs/verification/minimax_m3_story_package.json`
- Generate: `outputs/verification/minimax_m3_story_package_summary.json`

**Steps:**
1. Run all local tests and compile checks.
2. Execute exactly one real M3 request.
3. Require valid JSON, finish reason other than `length`, Pydantic success, and all brief limits.
4. Record story character count and story-text character length for evaluation.

No Git commit steps are included because the existing `.git` directory is not a valid Git repository.
