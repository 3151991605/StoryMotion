from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from storymotion.models import StoryMotionBundle


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "valid_storymotion_bundle.json"
sys.path.insert(0, str(SCRIPTS_DIR))

import verify_minimax_story_package as probe  # noqa: E402


@pytest.fixture
def bundle() -> StoryMotionBundle:
    return StoryMotionBundle.model_validate_json(
        FIXTURE_PATH.read_text(encoding="utf-8")
    )


def test_story_matches_brief(bundle: StoryMotionBundle) -> None:
    probe.validate_story_against_brief(bundle.story, bundle.brief)


def test_story_rejects_brief_character_limit(bundle: StoryMotionBundle) -> None:
    limited_brief = bundle.brief.model_copy(update={"max_characters": 1})
    with pytest.raises(ValueError, match="character limit"):
        probe.validate_story_against_brief(bundle.story, limited_brief)


def test_story_prompt_is_compact_and_complete() -> None:
    prompt = probe.SYSTEM_PROMPT
    assert "500–650" in prompt
    assert "2 个角色" in prompt
    assert "1 个地点" in prompt
    for beat_type in ("hook", "setup", "conflict", "reversal", "cliffhanger"):
        assert beat_type in prompt
