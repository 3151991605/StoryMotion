# Prop Continuity and Clean Keyframes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent chained keyframe noise and keep recurring story props visually identical across all relevant shots.

**Architecture:** Add backward-compatible prop records to the story, screenplay, scene, and shot contracts. Generate one clean prop model sheet per important prop, then generate every keyframe independently from canonical character, prop, and scene references; never use a generated keyframe as another keyframe's input.

**Tech Stack:** Python 3.10+, Pydantic v2, Streamlit, pytest, Wan multi-reference image generation.

---

### Task 1: Add backward-compatible prop contracts

**Files:**
- Modify: `src/storymotion/models/base.py`
- Modify: `src/storymotion/models/story.py`
- Modify: `src/storymotion/models/screenplay.py`
- Modify: `src/storymotion/models/shot.py`
- Modify: `src/storymotion/models/bundle.py`
- Modify: `src/storymotion/models/__init__.py`
- Test: `tests/test_contract_validation.py`

**Steps:**
1. Add a `PropId` pattern and `StoryProp` model with name, visual description, aliases, and immutable continuity features.
2. Add default-empty prop collections to story and screenplay packages.
3. Add default-empty `prop_ids` to scenes and shots so old bundles remain valid.
4. Validate duplicate IDs and all cross-layer prop references.
5. Run contract tests and confirm old fixtures still validate.

### Task 2: Generate or infer the production prop list

**Files:**
- Modify: `src/storymotion/services/narrative_generator.py`
- Test: `tests/test_narrative_generator.py`

**Steps:**
1. Update the generation contract to request important recurring or plot-bearing props and scene `prop_ids`.
2. Normalize model-provided props into stable `prop_NNN` records.
3. Add a conservative Chinese keyword fallback for common continuity-critical objects such as phones, letters, photos, keys, badges, weapons, medicine, jewellery, watches, umbrellas, and bags.
4. Infer scene prop references by IDs, names, aliases, and scene text.
5. Test explicit phone props, inferred phone props, and scenes without props.

### Task 3: Carry prop references into storyboard shots

**Files:**
- Modify: `src/storymotion/providers/rule_shot_provider.py`
- Test: `tests/test_rule_shot_provider.py`

**Steps:**
1. Copy each scene's `prop_ids` to every shot derived from that scene.
2. Add immutable prop descriptions to image and video continuity prompts.
3. Test that only props present in a scene reach its shots.

### Task 4: Generate prop model sheets and remove keyframe chaining

**Files:**
- Modify: `src/storymotion/services/visual_reference_renderer.py`
- Test: `tests/test_visual_reference_renderer.py`

**Steps:**
1. Add `prop_frames` to visual assets and manifests.
2. Generate a clean white-background multi-view model sheet for each prop.
3. Include relevant prop frames in scene and keyframe multi-reference requests.
4. Remove `previous_keyframe` from every image request.
5. Seed keyframes by `shot_id` so camera compositions can change without identity drift.
6. Test that no keyframe contains a prior keyframe data URL and that prop references are reused.

### Task 5: Show prop references in the frontend

**Files:**
- Modify: `streamlit_app.py`

**Steps:**
1. Load the `props` manifest group.
2. Add a “关键道具设定” section between character and scene assets.
3. Keep old manifests compatible when the group is absent.
4. Load the page and verify there are no fatal Streamlit errors.

### Task 6: Regression verification

**Files:**
- Test: `tests/`

**Steps:**
1. Run focused model, narrative, storyboard, and renderer tests.
2. Run `pytest -q`.
3. Run `git diff --check`.
4. Confirm no live image or video API is invoked during automated tests.
