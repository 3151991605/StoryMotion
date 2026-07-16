# Rule Shot Provider and Mock Video Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Generate a strict six-shot `ShotPackage` without PenShot or model calls, then render it as a validated 60-second vertical Mock MP4.

**Architecture:** `RuleShotProvider` deterministically splits each screenplay scene into clips of at most 10 seconds and builds prompts from canonical character/location data. `MockVideoProvider` is a separate FFmpeg-backed renderer that turns the resulting shots into colored vertical cards with Chinese subtitles. Both providers depend only on StoryMotion protocols and can be replaced independently.

**Tech Stack:** Python 3.11, Pydantic v2, pytest, FFmpeg/ffprobe, ASS subtitles, H.264 MP4.

---

### Task 1: Implement RuleShotProvider with TDD

**Files:**
- Create: `src/storymotion/providers/rule_shot_provider.py`
- Create: `src/storymotion/providers/__init__.py`
- Create: `tests/test_rule_shot_provider.py`

**Steps:**

1. Write failing tests for six-shot segmentation, 10-second maximum duration, exact per-scene totals, canonical character references, and prompt completeness.
2. Confirm tests fail because the provider does not exist.
3. Implement deterministic splitting and prompt templates.
4. Run targeted and full tests.

Expected: six shots totaling 60 seconds; scene 003 is the only scene split into two shots.

### Task 2: Generate and verify the rule-based ShotPackage

**Files:**
- Create: `scripts/verify_rule_shot_provider.py`
- Create: `outputs/verification/rule_shots/shot_package.json`
- Create: `outputs/verification/rule_shot_provider_summary.json`

**Steps:**

1. Load the repaired ScreenplayPackage.
2. Generate ShotPackage without network calls.
3. Construct and validate the complete StoryMotionBundle.
4. Save shot metrics and prompt completeness evidence.

### Task 3: Install a workspace-local FFmpeg runtime

**Files:**
- Create: `.tools/ffmpeg/`

**Steps:**

1. Download a trusted Windows static build into the workspace.
2. Verify `ffmpeg -version`, `ffprobe -version`, H.264 encoding, ASS subtitle filtering, and Chinese font availability.
3. Record the exact binary path and version.

Expected: FFmpeg works without modifying the system PATH.

### Task 4: Render and validate Mock MP4

**Files:**
- Create: `src/storymotion/providers/mock_video_provider.py`
- Create: `scripts/render_mock_video.py`
- Create: `tests/test_mock_video_provider.py`
- Create: `outputs/verification/mock_video/storymotion_mock.mp4`
- Create: `outputs/verification/mock_video_summary.json`

**Steps:**

1. Generate an ASS timeline containing title, shot/scene ID, duration, camera, and concise visual text.
2. Render six deterministic color segments at 720×1280 and concatenate them with FFmpeg.
3. Burn Chinese subtitles and encode H.264 MP4.
4. Verify with ffprobe: 60-second duration, 720×1280 resolution, valid video stream, six timeline entries, and expected frame rate.

Git worktree and commit steps are omitted because the workspace is not a valid Git repository.
