from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from storymotion.models import ScenePackage, StoryMotionBundle


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import verify_minimax_screenplay_adapter as probe  # noqa: E402


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json"


@pytest.fixture
def bundle() -> StoryMotionBundle:
    return StoryMotionBundle.model_validate_json(
        FIXTURE_PATH.read_text(encoding="utf-8")
    )


def test_payload_requests_scene_only_anthropic_output(
    bundle: StoryMotionBundle,
) -> None:
    payload = probe.build_payload(bundle.story)

    assert payload["model"] == "MiniMax-M2.7"
    assert payload["max_tokens"] == 4096
    assert "max_completion_tokens" not in payload
    assert "顶层必须严格包含且只包含 target_duration、scenes" in probe.SYSTEM_PROMPT
    assert "不要重复输出 title、characters、locations" in probe.SYSTEM_PROMPT
    assert payload["messages"][0]["role"] == "user"


def test_context_is_compact_but_keeps_story_and_ids(
    bundle: StoryMotionBundle,
) -> None:
    context = probe.build_screenplay_context(bundle.story)
    serialized = json.dumps(context, ensure_ascii=False)

    assert context["title"] == bundle.story.title
    assert context["story_text"] == bundle.story.story_text
    assert context["characters"][0]["id"] == "char_001"
    assert context["locations"][0]["id"] == "loc_001"
    assert "visual_prompt_zh" not in serialized
    assert "visual_prompt_en" not in serialized


def test_story_specific_validation_requires_beat_duration_mapping(
    bundle: StoryMotionBundle,
) -> None:
    package = ScenePackage(
        target_duration=bundle.screenplay.target_duration,
        scenes=bundle.screenplay.scenes,
    )
    with pytest.raises(ValueError, match="exactly 5 scenes"):
        probe.validate_for_story(package, bundle.story)


def test_spoken_pacing_rejects_unplayable_voiceover(
    bundle: StoryMotionBundle,
) -> None:
    scene = bundle.screenplay.scenes[0].model_copy(
        update={"duration": 10, "voiceover": "旁" * 41}
    )
    with pytest.raises(ValueError, match="pacing limit"):
        probe.validate_spoken_pacing(scene)
