# Character Identity and Expression Consistency Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve character aesthetics, facial acting, and cross-shot identity consistency while keeping the current MiniMax image provider usable and preparing a clean path to stronger open-source backends.

**Architecture:** Split immutable identity, visual style, shot composition, and acting into separate prompt layers. Use a stable face anchor and character-level seed for single-character keyframes, keep full-body turnarounds as wardrobe references, and persist enough metadata for later provider-specific multi-reference generation. The first phase remains provider-agnostic; a later adapter can connect StoryMaker, StoryDiffusion, or ComfyUI without rewriting storyboard logic.

**Tech Stack:** Python 3.9+, Pydantic, MiniMax image API, pytest, Streamlit. Research references: StoryDiffusion, StoryMaker, Story2Board, InstantID.

---

## Research Basis

- [StoryDiffusion](https://github.com/HVision-NKU/StoryDiffusion): shares consistent self-attention across a sequence instead of regenerating identity independently per panel.
- [StoryMaker](https://github.com/FireRedTeam/StoryMaker): combines face information, a subject mask, and full-person features to preserve face, hair, clothes, and body, including multi-character scenes.
- [Story2Board](https://github.com/DavidDinkevich/Story2Board): uses a shared reference-panel latent and attention-value mixing to balance identity stability with cinematic layout diversity.
- [InstantID](https://github.com/instantX-research/InstantID): separates identity-conditioning strength from text/control strength, supporting the identity-versus-performance split used in this plan.

The current MiniMax API exposes one subject-reference image, so phase one emulates these principles through stable anchors, separated prompt contracts, and deterministic character seeds. True multi-reference feature sharing remains a backend capability, not a prompt-only fix.

---

### Task 1: Lock expected prompt behavior with failing tests

**Files:**
- Modify: `tests/test_visual_reference_renderer.py`

**Steps:**
1. Add a test asserting immutable identity text does not contain the character's temporary facial expression.
2. Add a test asserting keyframe prompts contain separate `IDENTITY`, `ACTING`, `COMPOSITION`, and `AESTHETIC` contracts.
3. Assert a single-character keyframe uses the face identity anchor as its reference.
4. Assert all shots of one character reuse a character-level seed.
5. Run the focused test and confirm it fails before implementation.

### Task 2: Separate visual identity from temporary acting

**Files:**
- Modify: `src/storymotion/services/visual_reference_renderer.py`
- Test: `tests/test_visual_reference_renderer.py`

**Steps:**
1. Add a conservative helper that removes expression/action clauses from canonical character prose.
2. Build a compact immutable identity contract from age, hair, wardrobe, distinctive features, and static design only.
3. Keep identity anchors neutral so expressions do not become permanent character traits.
4. Run the focused test and confirm it passes.

### Task 3: Build compact cinematic keyframe prompts

**Files:**
- Modify: `src/storymotion/services/visual_reference_renderer.py`
- Test: `tests/test_visual_reference_renderer.py`

**Steps:**
1. Replace the long concatenated `shot.image_prompt` path with a bounded prompt assembled from structured keyframe fields.
2. Add an acting contract that explicitly controls eyebrows, eyelids, gaze, mouth/jaw, head angle, shoulders, hands, and emotional intensity.
3. Add a composition contract using shot type, camera movement, start state, and visible result.
4. Add a stronger aesthetic contract for polished adult 2D Chinese animation and reject generic doll-like faces, blank expressions, beauty filters, and inconsistent linework.
5. Preserve no-text/no-watermark constraints without repeating them across every layer.

### Task 4: Improve reference and seed selection

**Files:**
- Modify: `src/storymotion/services/visual_reference_renderer.py`
- Test: `tests/test_visual_reference_renderer.py`

**Steps:**
1. Use the square face anchor as the identity reference for the first keyframe of a scene.
2. Reuse the preceding approved keyframe when the scene and cast are unchanged, following the shared-panel anchoring principle used by StoryDiffusion and Story2Board.
3. Keep the turnaround as the reference for environment staging and as a future secondary wardrobe input.
4. Derive the keyframe seed from the primary character ID rather than the shot ID.
5. Keep scene-only shots deterministic from the scene ID.
6. Document the one-reference limitation for multi-character MiniMax shots.

### Task 5: Verify behavior and protect existing output reuse

**Files:**
- Test: `tests/test_visual_reference_renderer.py`
- Test: `tests/test_visual_generation_contract.py`
- Test: `tests/test_prompt_director.py`

**Steps:**
1. Run focused visual-reference tests.
2. Run prompt and visual-contract regression tests.
3. Run `git diff --check` and compile changed Python files.
4. Confirm existing generated files are reused and no paid image calls occur during tests.

### Task 6: Generate an A/B comparison with the same story

**Files:**
- Output only: `outputs/character_consistency_ab_*`

**Steps:**
1. Preserve the current images as the baseline.
2. Generate only one character anchor, turnaround, and three representative keyframes with the improved prompts.
3. Compare identity, expression accuracy, aesthetics, and wardrobe consistency side by side.
4. Stop before video generation.

### Task 7: Prepare the stronger-backend path

**Files:**
- Future create: `src/storymotion/providers/multi_reference_image.py`
- Future modify: `src/storymotion/models/media.py`

**Steps:**
1. Extend image requests to support typed references: face, body/wardrobe, previous panel, style, and per-character mask.
2. Implement an optional ComfyUI/StoryMaker or StoryDiffusion adapter on a CUDA server.
3. Keep MiniMax as a fallback provider for users without a local GPU.
4. Evaluate with a fixed storyboard benchmark before making the new backend default.

## A/B Validation Result

Real MiniMax image generation was run against the same three-shot sequence in `outputs/character_consistency_ab_20260722_155135`.

- The original independent-shot strategy produced weak expressions and visible facial drift.
- Separating identity from acting and sharing a character seed made the three keyframes substantially more alike.
- Moving the positive 2D aesthetic contract to the front removed an unintended 3D-rendered look.
- A text-only closed accessory inventory did not reliably prevent invented glasses.
- Reusing the preceding keyframe as the next panel anchor removed the invented glasses and improved face/hair continuity.
- MiniMax still changed full-length jeans into shorts in one frame. This confirms that its one-reference API cannot guarantee simultaneous face, clothing, composition, and expression locking. A typed multi-reference backend remains necessary for production-level exactness.
