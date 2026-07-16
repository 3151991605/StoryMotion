# MiniMax Structured Output Stability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Verify that MiniMax-M3 can produce the canonical StoryMotion `ProjectBrief` in three consecutive requests.

**Architecture:** Keep the network probe in `scripts/`, but import the canonical Pydantic model from the installed `storymotion` package. Each run is independently parsed and validated, with safe metrics and validated JSON saved under ignored verification outputs.

**Tech Stack:** Python 3.11, standard-library HTTP client, Pydantic 2, pytest.

---

### Task 1: Write failing probe contract tests

**Files:**
- Create: `tests/test_minimax_structured_probe.py`

**Steps:**
1. Test that canonical flat ProjectBrief output validates.
2. Test that the previous nested `constraints` shape is rejected.
3. Test that the prompt names all canonical top-level fields.
4. Run the focused tests and confirm failure against the old probe.

### Task 2: Refactor the probe to the canonical model

**Files:**
- Modify: `scripts/verify_minimax_structured_output.py`

**Steps:**
1. Replace the manual validator with `ProjectBrief.model_validate`.
2. Update the prompt to require flat constraint fields.
3. Add `--runs` with an allowed range of 1 through 3 and a default of 1.
4. Save one validated JSON file per run plus a summary containing latency, model, and usage.
5. Run all local tests and compile checks.

### Task 3: Execute the three-run stability gate

**Files:**
- Generate: `outputs/verification/minimax_m3_project_brief_run_01.json`
- Generate: `outputs/verification/minimax_m3_project_brief_run_02.json`
- Generate: `outputs/verification/minimax_m3_project_brief_run_03.json`
- Generate: `outputs/verification/minimax_m3_stability_summary.json`

**Steps:**
1. Run the probe once with `--runs 3`.
2. Require three successful Pydantic validations.
3. Report success rate, total token usage, and latency range.
4. Do not retry failed requests automatically; failures are feasibility evidence.

No Git commit steps are included because the existing `.git` directory is not a valid Git repository.
