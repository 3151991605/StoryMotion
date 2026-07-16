from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from storymotion.models import StoryMotionBundle


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import repair_minimax_screenplay_voiceover as repair_probe  # noqa: E402


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json"


@pytest.fixture
def bundle() -> StoryMotionBundle:
    return StoryMotionBundle.model_validate_json(
        FIXTURE_PATH.read_text(encoding="utf-8")
    )


def test_repair_payload_is_small_and_scene_scoped(
    bundle: StoryMotionBundle,
) -> None:
    payload = repair_probe.build_payload(bundle.screenplay, "scene_001")

    assert payload["model"] == "MiniMax-M2.7"
    assert payload["max_tokens"] == 1024
    assert "scene_001" in payload["messages"][0]["content"]
    assert "scenes" not in payload["messages"][0]["content"]


def test_repair_protocol_rejects_more_than_40_characters() -> None:
    with pytest.raises(ValidationError, match="at most 40 characters"):
        repair_probe.VoiceoverRepair(
            scene_id="scene_001",
            voiceover="旁" * 41,
        )


def test_apply_repair_changes_only_target_voiceover(
    bundle: StoryMotionBundle,
) -> None:
    before = bundle.screenplay
    repair = repair_probe.VoiceoverRepair(
        scene_id="scene_001",
        voiceover="死亡瞬间，时间倒退十秒。",
    )

    after = repair_probe.apply_voiceover_repair(before, repair)

    assert after.scenes[0].voiceover == repair.voiceover
    assert after.scenes[0].action == before.scenes[0].action
    assert after.scenes[1:] == before.scenes[1:]
    assert after.total_scene_duration == before.total_scene_duration
