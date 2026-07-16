# MiniMax Bounded Story Graph Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Verify that four bounded MiniMax-M3 nodes can produce and assemble a canonical StoryPackage without any node exceeding the response limit.

**Architecture:** Add strict intermediate models for characters, plot, and story draft. Run Worldview, Characters, Plot, and Writer sequentially, persist every validated node result, and assemble the final StoryPackage locally.

**Tech Stack:** Python 3.11, Pydantic 2, standard-library HTTP client, pytest.

---

### Task 1: Add failing intermediate-contract and assembler tests

**Files:**
- Create: `tests/test_story_assembly.py`
- Create: `tests/test_minimax_story_graph_probe.py`

**Steps:**
1. Test strict CharacterPackage, PlotPlan, and StoryDraft parsing.
2. Test deterministic StoryPackage assembly from validated components.
3. Test protagonist, character-limit, and story-length failures.
4. Test that the graph exposes four nodes in the required order.
5. Run focused tests and confirm missing modules fail collection.

### Task 2: Implement intermediate models and assembler

**Files:**
- Create: `src/storymotion/models/intermediate.py`
- Create: `src/storymotion/services/__init__.py`
- Create: `src/storymotion/services/story_assembler.py`
- Modify: `src/storymotion/models/story.py`
- Modify: `src/storymotion/models/__init__.py`

**Steps:**
1. Centralize canonical beat order and duration validation.
2. Implement strict intermediate packages with unique IDs and text bounds.
3. Implement local StoryPackage assembly with ProjectBrief cross-checks.
4. Run focused unit tests.

### Task 3: Implement the four-node feasibility probe

**Files:**
- Create: `scripts/verify_minimax_story_graph.py`

**Steps:**
1. Define compact prompts for Worldview, CharacterPackage, PlotPlan, and StoryDraft.
2. Pass only validated JSON state into each downstream node.
3. Use a 120-second timeout and 2048 completion-token cap per node.
4. Stop on the first failed or truncated node without retrying.
5. Save per-node JSON, raw failure evidence, latency, finish reason, and usage.
6. Assemble and save the final StoryPackage only after all nodes pass.

### Task 4: Execute and assess the graph

**Files:**
- Generate: `outputs/verification/story_graph/*.json`
- Generate: `outputs/verification/minimax_m3_story_graph_summary.json`

**Steps:**
1. Run all tests and compile checks.
2. Execute the graph once, allowing at most four M3 requests.
3. Report the last completed node, total requests, total usage, latency, and final StoryPackage validation status.

No Git commit steps are included because the existing `.git` directory is not a valid Git repository.

