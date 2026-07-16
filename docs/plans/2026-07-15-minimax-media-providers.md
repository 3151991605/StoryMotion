# MiniMax Media Providers Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add strict, offline-tested MiniMax image and Hailuo asynchronous video
providers for a one-shot real media validation.

**Architecture:** StoryMotion-owned request, task, and result models isolate the
application from MiniMax payloads. An injectable bounded transport makes all
contracts and failure paths testable without network access. Live submission
is kept in a separate explicit probe.

**Tech Stack:** Python 3.11, Pydantic 2, urllib, pytest, MiniMax image-01 and
MiniMax-Hailuo-2.3 APIs.

---

### Task 1: Define media contracts

**Files:**
- Create: `src/storymotion/models/media.py`
- Modify: `src/storymotion/models/__init__.py`
- Create: `src/storymotion/providers/media.py`
- Test: `tests/test_media_models.py`

1. Write failing validation tests for image requests, video requests, task state,
   and successful result invariants.
2. Run the test and confirm imports fail.
3. Implement strict models and provider protocols.
4. Run focused tests.

### Task 2: Implement bounded MiniMax media transport

**Files:**
- Create: `src/storymotion/providers/minimax_media.py`
- Test: `tests/test_minimax_media_transport.py`

1. Test JSON request construction, response size, malformed JSON, HTTP errors,
   secret-safe errors, and HTTPS download allowlisting.
2. Implement urllib transport with finite timeouts and size limits.
3. Run focused tests.

### Task 3: Implement MiniMax image provider

**Files:**
- Modify: `src/storymotion/providers/minimax_media.py`
- Test: `tests/test_minimax_image_provider.py`

1. Test the exact image-01 payload, base64 validation, image magic bytes, output
   file creation, and no-retry failures.
2. Implement synchronous generation to a local image artifact.
3. Run focused tests.

### Task 4: Implement Hailuo asynchronous video provider

**Files:**
- Modify: `src/storymotion/providers/minimax_media.py`
- Modify: `src/storymotion/providers/__init__.py`
- Test: `tests/test_hailuo_video_provider.py`

1. Test text-to-video and image-to-video submit payloads.
2. Test all official status mappings, task ID matching, account errors, failed
   tasks, file retrieval, and secure download delegation.
3. Implement submit, get_status, get_result, and download with no polling loop or
   retry.
4. Export public provider types and run focused tests.

### Task 5: Prepare the one-shot probe

**Files:**
- Create: `scripts/verify_hailuo_single_shot.py`
- Create: `tests/test_hailuo_single_shot_probe.py`

1. Load `shot_001` from the validated MiniMax ShotPackage.
2. Add dry-run as the default; require `--submit` to make a paid video request.
3. Bound overall deadline, polling interval, file size, and request count.
4. Save only sanitized summary, generated first frame, and resulting MP4.
5. Test dry-run and failure paths without network access.

### Task 6: Verify

1. Run all focused media tests.
2. Run the complete pytest suite.
3. Scan source, tests, docs, scripts, and outputs for the configured API key.
4. Review URL, file, and secret-handling paths against the security checklist.
