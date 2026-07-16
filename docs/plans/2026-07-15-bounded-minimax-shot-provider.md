# Bounded MiniMax Shot Provider Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build and verify a first-party single-request MiniMax M3 storyboard
provider with deterministic structure and RuleShot fallback.

**Architecture:** A deterministic RuleShot result supplies immutable shot
structure. MiniMax supplies creative enrichment only. Strict local validation
assembles the final `ShotPackage`, and expected provider failures can fall back
to RuleShot without hiding programming errors.

**Tech Stack:** Python 3.11, Pydantic 2, urllib, pytest, MiniMax
OpenAI-compatible chat completions.

---

### Task 1: Define offline behavior with tests

**Files:**
- Create: `tests/test_minimax_shot_provider.py`

1. Add a recording fake transport and valid MiniMax response fixture.
2. Test deterministic shot IDs, durations, scene IDs, and character IDs.
3. Test exactly one request and the expected bounded payload.
4. Test reasoning-block removal, JSON extraction, and canonical reordering.
5. Test missing, duplicate, unknown, truncated, and invalid output failures.
6. Test that invalid output causes no retry.
7. Test configured fallback and unrelated-error propagation.
8. Run the focused test file and confirm it fails because implementation is
   absent.

### Task 2: Implement the provider and transport

**Files:**
- Create: `src/storymotion/providers/minimax_shot_provider.py`
- Modify: `src/storymotion/providers/penshot_sidecar.py`
- Modify: `src/storymotion/providers/__init__.py`

1. Add strict enrichment response models and classified errors.
2. Add an injectable chat transport protocol and bounded urllib transport.
3. Build deterministic skeleton and compact screenplay context.
4. Make one request with no internal retry.
5. Parse and validate the response, then assemble from immutable structure.
6. Generalize fallback to accept an explicit expected-exception tuple while
   preserving its existing Sidecar-only default.
7. Export the new public provider types.

### Task 3: Verify offline behavior

**Files:**
- Test: `tests/test_minimax_shot_provider.py`
- Test: all files under `tests/`

1. Run focused tests until green.
2. Run the entire test suite.
3. Scan changed files and generated artifacts for accidental API-key leakage.

### Task 4: Add a bounded real-call probe

**Files:**
- Create: `scripts/verify_minimax_shot_provider.py`
- Create: `tests/test_minimax_shot_provider_probe.py`

1. Add safe allowlisted environment loading.
2. Make the probe perform exactly one provider request with no retry.
3. Write a validated ShotPackage on success and a sanitized summary on either
   success or failure.
4. Unit-test that the probe never writes the API key and reports failures
   without a second request.

### Task 5: Execute one real MiniMax M3 validation

**Files:**
- Create: `outputs/verification/minimax_shot_provider_summary.json`
- Create on success:
  `outputs/verification/minimax_shot_provider_package.json`

1. Run the probe once against the configured MiniMax endpoint.
2. Validate the generated ShotPackage locally.
3. Run the full regression suite again.
4. Record the feasibility result and decide whether the next phase should be
   Hailuo single-shot generation or prompt-quality iteration.
