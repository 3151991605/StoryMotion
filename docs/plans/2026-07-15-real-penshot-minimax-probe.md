# Real PenShot MiniMax Probe Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Determine whether an isolated PenShot 0.3.4 runtime can use StoryMotion's validated MiniMax-M3 OpenAI-compatible access without exposing the main application environment.

**Architecture:** Install the already archived MIT wheel into a workspace-local Python 3.11 virtual environment. Apply two documented compatibility patches only inside that experimental environment, run from a deep working directory that cannot be found by PenShot's two-level `.env` search, inject only the required MiniMax variables into the child process, and persist sanitized JSON evidence.

**Tech Stack:** Python 3.11, PenShot 0.3.4, LangChain OpenAI adapter, MiniMax OpenAI-compatible API, Pydantic v2.

---

### Task 1: Create isolated dependency environment

**Files:**
- Create: `.tools/penshot/sidecar_venv/`
- Use: `.tools/penshot/penshot-0.3.4-py3-none-any.whl`

**Steps:** Create the virtual environment; install the local wheel plus its LLM-provider extra; run `pip check`; record exact versions. Do not import PenShot yet.

### Task 2: Apply and verify compatibility patches

**Files:**
- Modify only inside: `.tools/penshot/sidecar_venv/Lib/site-packages/penshot/`
- Create: `scripts/verify_penshot_minimax_runtime.py`
- Test: `tests/test_penshot_minimax_runtime.py`

**Steps:** Patch `AIConfig` fields to use `default_factory`; classify `minimaxi.com` as OpenAI-compatible; add a verification script that masks credentials and uses an isolated working directory; unit-test payload/config construction without calling the network.

### Task 3: Import and client-construction smoke test

**Files:**
- Create: `outputs/verification/penshot_runtime_import_summary.json`

**Steps:** Start a clean child process with only the required environment variables, import PenShot, construct `ShotConfig` and its LLM client, and persist sanitized evidence. Stop if this fails.

### Task 4: One bounded MiniMax-M3 call through PenShot

**Files:**
- Create: `outputs/verification/penshot_minimax_client_summary.json`

**Steps:** Invoke one short prompt through the exact LLM object PenShot would use; limit output tokens and timeout; store model, latency, finish state and a short sanitized response preview. Never store headers or credentials.

### Task 5: Decide on full storyboard execution

**Files:**
- Update: `outputs/verification/penshot_feasibility_summary.json`
- Update: `docs/research/2026-07-15-open-source-reference-review.md`

**Steps:** If the single call succeeds, estimate full-workflow request count and compatibility risks before running it. If it fails, preserve the blocker and keep `RuleShotProvider` as the active path.
