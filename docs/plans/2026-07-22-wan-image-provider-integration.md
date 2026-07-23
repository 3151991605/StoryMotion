# Wan Image Provider Integration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Use MiniMax for narrative generation, Wan 2.7 for every visual-reference image, and keep Hailuo as the unchanged video provider.

**Architecture:** Add a provider implementing the existing `ImageProvider` contract and a restricted urllib transport for Alibaba Model Studio. The Streamlit provider factory prefers Wan when `DASHSCOPE_API_KEY` is set and otherwise preserves the MiniMax fallback. `VisualReferenceRenderer` remains provider-agnostic and continues to create identity anchors, turnarounds, scenes, and all shot keyframes.

**Tech Stack:** Python 3.11+, urllib, Pydantic models, pytest, Alibaba Model Studio Wan 2.7 synchronous API.

---

### Task 1: Define and test the Wan transport contract

**Files:**
- Create: `tests/test_wan_media.py`
- Create: `src/storymotion/providers/wan_media.py`

1. Test accepted official Beijing hosts and rejected non-HTTPS/unapproved hosts.
2. Test request payload mapping for text-to-image and reference-image editing.
3. Test API error and malformed-response handling.
4. Test that only approved Alibaba OSS result URLs can be downloaded.

### Task 2: Implement the provider

**Files:**
- Create: `src/storymotion/providers/wan_media.py`
- Modify: `src/storymotion/providers/__init__.py`

1. Implement authenticated JSON POST requests with bounded responses.
2. Map StoryMotion aspect ratios to explicit Wan 1K dimensions.
3. Send the optional reference image before the prompt.
4. Download, validate, and atomically save PNG/JPEG/WEBP output.
5. Return `GeneratedImage(provider="wan", ...)`.

### Task 3: Select Wan in the application

**Files:**
- Modify: `streamlit_app.py`
- Modify: `.env.example`

1. Prefer Wan when `DASHSCOPE_API_KEY` is configured.
2. Preserve MiniMax image fallback for collaborators without a Wan key.
3. Update UI quota labels so they describe the active image provider.

### Task 4: Verify locally

Run focused provider and visual-renderer tests, then `pytest -q tests`.

### Task 5: Run a live no-video workflow

**Files:**
- Create: `scripts/run_wan_no_video_test.py`

1. Generate a short story package with the configured MiniMax text model.
2. Limit the live sample to a small complete cast and 3-5 shots.
3. Generate every identity, turnaround, scene, and keyframe with Wan 2.7.
4. Save the bundle and reference manifest under `outputs/`.
5. Inspect all images for identity, clothing, expression, style, and multi-character separation.
