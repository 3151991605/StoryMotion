# Streamlit Demo Interface Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a polished local Streamlit dashboard that presents the verified StoryMotion pipeline, artifacts, storyboard, and Mock video truthfully.

**Architecture:** A framework-independent view-model module validates and formats existing verification artifacts. A thin Streamlit entry point renders an editorial single-page control room, while project configuration pins Streamlit as an optional UI dependency.

**Tech Stack:** Python 3.11, Pydantic 2, Streamlit 1.59, pytest, CSS

---

### Task 1: Define the UI view-model contract with tests

**Files:**
- Create: `src/storymotion/ui/__init__.py`
- Create: `src/storymotion/ui/demo_view_model.py`
- Create: `tests/test_demo_view_model.py`

**Step 1:** Write a failing test that loads the end-to-end bundle and summary.

**Step 2:** Assert four ordered stage records, six shot rows, a 60-second duration, Mock media status, and Hailuo quota status 2056.

**Step 3:** Add a missing-artifact test requiring a clear `FileNotFoundError`.

**Step 4:** Implement the minimal immutable view model and loader; run focused tests.

### Task 2: Add the Streamlit application and theme

**Files:**
- Create: `streamlit_app.py`
- Create: `.streamlit/config.toml`
- Modify: `pyproject.toml`

**Step 1:** Add `streamlit>=1.59,<2` under a `ui` optional dependency.

**Step 2:** Render the verified brief in the sidebar without loading secrets.

**Step 3:** Render the hero, production rail, story, screenplay, storyboard cards, and playable MP4.

**Step 4:** Add an explicit Hailuo quota warning and recovery guidance.

**Step 5:** Add cohesive responsive CSS and accessible labels.

### Task 3: Install and statically verify the UI

**Files:**
- Modify: project virtual environment only

**Step 1:** Install the project with the `ui` and `dev` extras.

**Step 2:** Run `python -m streamlit version` and require Streamlit 1.59.x or compatible.

**Step 3:** Run `python -m py_compile streamlit_app.py` and the focused view-model tests.

### Task 4: Launch and visually verify the dashboard

**Files:**
- No source changes unless visual defects are found.

**Step 1:** Launch Streamlit on localhost without opening an external browser.

**Step 2:** Inspect the page in the in-app browser at desktop width.

**Step 3:** Verify hero, stage rail, tabs, shot cards, video player, warning states, spacing, and contrast; fix defects before delivery.

**Step 4:** Run the full pytest suite and retain the local launch command for handoff.

> Note: this workspace is not a Git repository, so per-task commits are not applicable.
