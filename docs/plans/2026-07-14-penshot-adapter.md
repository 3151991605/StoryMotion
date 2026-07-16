# PenShot Adapter Feasibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Verify that PenShot 0.3.4 can accept the validated Chinese `ScreenplayPackage` and produce data that can be converted into StoryMotion's strict `ShotPackage`.

**Architecture:** Treat PenShot as an external provider behind an adapter. First inspect and import the pinned package, then isolate its raw result schema from StoryMotion models. The adapter converts raw fragments into canonical shots and performs local scene, character, prompt, and duration validation; a deterministic mock fixture remains available if the real SDK is blocked by infrastructure.

**Tech Stack:** Python 3.11, penshot 0.3.4, Pydantic v2, pytest, MiniMax OpenAI-compatible text API where supported.

---

### Task 1: Inspect and install the pinned PenShot package

**Files:**
- Download: `.tools/penshot/penshot-0.3.4-py3-none-any.whl`
- Modify: `pyproject.toml`

**Steps:**

1. Download the wheel without dependencies and inspect `METADATA`, exported modules, API factory, result models, and environment names.
2. Record dependency and infrastructure risks before installation.
3. Install `penshot==0.3.4` into the project virtual environment if its requirements are compatible.
4. Run an import-only smoke test for `penshot.api.create_penshot_agent`.

Expected: package imports under Python 3.11 without changing StoryMotion's own data protocol.

### Task 2: Define the PenShot boundary and adapter tests

**Files:**
- Create: `src/storymotion/adapters/penshot_adapter.py`
- Create: `src/storymotion/adapters/__init__.py`
- Create: `tests/test_penshot_adapter.py`

**Steps:**

1. Write failing tests using a raw PenShot-style fragment fixture.
2. Require 5-10 shots, unique IDs, known scene/character references, non-empty image/video prompts, and exact per-scene duration totals.
3. Implement the minimal conversion into `ShotPackage`.
4. Run targeted tests until they pass.

Expected: PenShot's raw shape cannot leak into the rest of the application.

### Task 3: Run a real Chinese SDK probe when infrastructure permits

**Files:**
- Create: `scripts/verify_penshot_sdk.py`
- Create: `outputs/verification/penshot/`

**Steps:**

1. Serialize the repaired screenplay into concise Chinese scene text.
2. Configure PenShot with the existing MiniMax text endpoint only if the SDK supports the required OpenAI-compatible provider path.
3. Submit one storyboard task, wait with a bounded timeout, and persist raw result/status evidence.
4. Do not retry automatically after an LLM, embedding, Redis, or schema failure.

Expected: either a real raw fragment result or an evidence-backed blocker classified by layer.

### Task 4: Convert and validate ShotPackage

**Files:**
- Create on success: `outputs/verification/penshot/shot_package.json`
- Create: `outputs/verification/penshot_feasibility_summary.json`

**Steps:**

1. Convert real fragments through the adapter; if Task 3 is infrastructure-blocked, convert the documented output fixture to prove the adapter independently.
2. Validate 5-10 shots, 60 total seconds, per-scene duration equality, prompt completeness, and character references.
3. Record `GO`, `GO_WITH_ADAPTER_ONLY`, or `NO_GO` with exact evidence.

Git worktree and commit steps are omitted because the workspace is not a valid Git repository.
