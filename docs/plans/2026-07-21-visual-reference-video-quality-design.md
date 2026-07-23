# Visual Reference Video Quality Implementation Plan

**Goal:** Improve image-to-video fidelity by generating reusable visual assets and a first-frame keyframe for every storyboard shot before submitting video jobs.

**Architecture:** A `VisualReferenceRenderer` creates character sheets, scene look frames, and shot keyframes in a persisted output directory. Each keyframe uses the previous asset as an image reference; the Hailuo renderer then uses the shot keyframe as that shot's first frame. Video prompts become explicit image-to-video directions: identity lock, initial state, one time-ordered action, spatial layout, camera movement, and visible final state.

**Tech stack:** Python 3.11, Pydantic, existing MiniMax image/video provider, pytest.

---

### Task 1: Specify and test visual-reference planning

**Files:**
- Create: `src/storymotion/services/visual_reference_renderer.py`
- Create: `tests/test_visual_reference_renderer.py`

1. Write tests for deterministic asset paths, all character/location/shot coverage, and reuse of existing image files.
2. Implement the reference renderer with a provider protocol and persisted directories: `characters/`, `scenes/`, `keyframes/`.
3. Generate character sheets first, scene frames second, then one keyframe per storyboard shot.

### Task 2: Make image-to-video prompts operational

**Files:**
- Modify: `src/storymotion/services/prompt_director.py`
- Modify: `tests/test_prompt_director.py`

1. Add a failing test that requires identity lock, temporal sequence, spatial constraint, camera direction, visible outcome, and no dialogue/text instructions.
2. Render each prompt from the keyframe contract with the exact shot duration.

### Task 3: Use each generated keyframe in rendering

**Files:**
- Modify: `src/storymotion/services/hailuo_video_renderer.py`
- Modify: `tests/test_hailuo_video_renderer.py`

1. Add a test that a supplied shot keyframe wins over a chained previous frame.
2. Accept the keyed first-frame mapping and persist it in rendering state.
3. Keep the existing lazy image generation only as a backward-compatible fallback.

### Task 4: Connect the production UI and document the behavior

**Files:**
- Modify: `streamlit_app.py`
- Modify: `README.md`

1. Prepare references before video submission when image credentials are configured.
2. Report asset generation progress and retain resumable outputs.
3. Document image-credit use and the generated artifact layout.

### Verification

Run the focused tests, then the full suite with Python 3.11:

```powershell
.venv\Scripts\python.exe -m pytest tests\test_visual_reference_renderer.py tests\test_prompt_director.py tests\test_hailuo_video_renderer.py -q
.venv\Scripts\python.exe -m pytest -q
```

The local virtual environment currently needs repair before these commands can run.
