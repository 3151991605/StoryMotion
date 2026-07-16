# StoryMotion Data Protocols Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Define and verify strict Pydantic contracts for ProjectBrief, StoryPackage, ScreenplayPackage, ShotPackage, and their cross-layer bundle.

**Architecture:** Keep domain models in separate modules under `src/storymotion/models`. Each package validates its own identifiers and durations. `StoryMotionBundle` performs integration checks across the four layers without coupling the models to LLM or PenShot response formats.

**Tech Stack:** Python 3.11, Pydantic 2, pytest, setuptools.

---

### Task 1: Project metadata and failing contract tests

**Files:**
- Create: `pyproject.toml`
- Create: `tests/test_data_protocols.py`

**Steps:**
1. Declare Python 3.11, Pydantic, and pytest dependencies.
2. Write a valid four-layer fixture in the test module.
3. Test valid parsing, unknown-field rejection, duration mismatch, and broken cross-layer references.
4. Run `pytest` and verify collection fails because `storymotion.models` does not exist.

### Task 2: Core package models

**Files:**
- Create: `src/storymotion/__init__.py`
- Create: `src/storymotion/models/base.py`
- Create: `src/storymotion/models/project.py`
- Create: `src/storymotion/models/story.py`
- Create: `src/storymotion/models/screenplay.py`
- Create: `src/storymotion/models/shot.py`
- Create: `src/storymotion/models/__init__.py`

**Steps:**
1. Add a strict base model that strips surrounding whitespace and rejects unknown fields.
2. Implement ProjectBrief bounds and typed story entities.
3. Implement package-level unique-ID, reference, and exact-duration validation.
4. Export the public model API.
5. Run focused tests and verify package-level tests pass.

### Task 3: Cross-layer bundle validation

**Files:**
- Create: `src/storymotion/models/bundle.py`
- Modify: `src/storymotion/models/__init__.py`
- Test: `tests/test_data_protocols.py`

**Steps:**
1. Implement `StoryMotionBundle` target-duration, limit, and ID-set checks.
2. Verify screenplay characters originate in StoryPackage.
3. Verify every shot references an existing screenplay scene and character.
4. Run the full test suite and verify all tests pass.

### Task 4: Serializable verification fixture

**Files:**
- Create: `tests/fixtures/valid_storymotion_bundle.json`

**Steps:**
1. Save the valid bundle as UTF-8 JSON.
2. Add a round-trip test loading the fixture and serializing it back to JSON.
3. Run `pytest -q` and `python -m compileall -q src tests`.
4. Record the test result in the handoff response.

No Git commit steps are included because the existing `.git` directory is not a valid Git repository.
