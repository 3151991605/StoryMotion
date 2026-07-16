from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from storymotion.models import StoryMotionBundle


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import verify_minimax_anthropic_writer as probe  # noqa: E402


def load_bundle() -> StoryMotionBundle:
    fixture = Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json"
    return StoryMotionBundle.model_validate_json(fixture.read_text(encoding="utf-8"))


def test_payload_uses_anthropic_shape_and_requested_limit() -> None:
    bundle = load_bundle()
    from storymotion.models import CharacterPackage, PlotPlan

    payload = probe.build_payload(
        bundle.brief,
        bundle.story.worldview,
        CharacterPackage(characters=bundle.story.characters),
        PlotPlan(target_duration=bundle.story.target_duration, beats=bundle.story.beats),
    )

    assert payload["model"] == "MiniMax-M2.7"
    assert payload["max_tokens"] == 4096
    assert "max_completion_tokens" not in payload
    assert payload["messages"][0]["role"] == "user"


def test_writer_context_omits_visual_prompt_bulk() -> None:
    bundle = load_bundle()
    from storymotion.models import CharacterPackage, PlotPlan

    context = probe.build_writer_context(
        bundle.brief,
        bundle.story.worldview,
        CharacterPackage(characters=bundle.story.characters),
        PlotPlan(target_duration=bundle.story.target_duration, beats=bundle.story.beats),
    )
    serialized = json.dumps(context, ensure_ascii=False)

    assert "visual_prompt_zh" not in serialized
    assert "appearance" not in serialized
    assert len(context["beats"]) == 5


def test_extract_text_blocks_ignores_thinking() -> None:
    response = {
        "content": [
            {"type": "thinking", "thinking": "internal"},
            {"type": "text", "text": '{"title":"ok"}'},
        ]
    }
    assert probe.extract_text_blocks(response) == '{"title":"ok"}'


def test_validate_draft_rejects_more_than_650_characters() -> None:
    with pytest.raises(ValueError, match="500-650"):
        probe.validate_draft(
            {"title": "标题", "logline": "梗概", "story_text": "字" * 651}
        )
