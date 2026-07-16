# PenShot Sidecar Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add and verify a dependency-free StoryMotion client/provider boundary for an isolated PenShot HTTP sidecar.

**Architecture:** Define strict request/status models, use an injectable JSON HTTP transport, poll with a bounded deadline, adapt successful raw results to `ShotPackage`, and wrap it with an explicit `RuleShotProvider` fallback. No PenShot code runs in the StoryMotion process.

**Tech Stack:** Python 3.11 standard library, Pydantic v2, pytest.

---

### Task 1: Contract models and HTTP client

**Files:**
- Create: `src/storymotion/providers/penshot_sidecar.py`
- Test: `tests/test_penshot_sidecar.py`

**Step 1:** Write failing tests for submit payloads, status parsing, completed results, remote failure, malformed responses, timeout, and cancellation.

**Step 2:** Run `pytest tests/test_penshot_sidecar.py -q` and confirm imports/tests fail.

**Step 3:** Implement strict contract models, transport errors, a standard-library JSON transport, and bounded polling.

**Step 4:** Run `pytest tests/test_penshot_sidecar.py -q` and confirm the client tests pass.

### Task 2: Provider adaptation and fallback

**Files:**
- Modify: `src/storymotion/providers/penshot_sidecar.py`
- Modify: `src/storymotion/providers/__init__.py`
- Test: `tests/test_penshot_sidecar.py`

**Step 1:** Add failing tests proving successful data flows through the existing adapter and classified sidecar failures fall back to the rule provider.

**Step 2:** Implement `PenShotSidecarProvider` and `FallbackShotProvider` without catching unrelated exceptions.

**Step 3:** Run the focused test module and confirm all cases pass.

### Task 3: Loopback contract verification

**Files:**
- Test: `tests/test_penshot_sidecar_http.py`

**Step 1:** Build a local `ThreadingHTTPServer` fixture with no external network access.

**Step 2:** Verify POST, GET, DELETE, JSON encoding, task paths, and non-2xx error normalization using the real standard-library transport.

**Step 3:** Run `pytest tests/test_penshot_sidecar_http.py -q` and confirm all cases pass.

### Task 4: Regression verification

**Files:**
- Modify if needed: `docs/research/2026-07-15-open-source-reference-review.md`

**Step 1:** Run the focused Sidecar and adapter tests.

**Step 2:** Run the complete test suite with `pytest -q`.

**Step 3:** Record the exact results and any remaining real-PenShot prerequisites.
