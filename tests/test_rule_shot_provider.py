from __future__ import annotations

from pathlib import Path

import pytest

from storymotion.models import ScreenplayPackage, StoryMotionBundle
from storymotion.providers import RuleShotProvider


SCREENPLAY_FILE = (
    Path(__file__).resolve().parents[1]
    / "outputs"
    / "verification"
    / "screenplay"
    / "screenplay_package_repaired.json"
)


@pytest.fixture
def screenplay() -> ScreenplayPackage:
    return ScreenplayPackage.model_validate_json(
        SCREENPLAY_FILE.read_text(encoding="utf-8")
    )


def test_generates_six_bounded_shots(screenplay: ScreenplayPackage) -> None:
    package = RuleShotProvider(max_shot_duration=10).generate(screenplay)

    assert len(package.shots) == 6
    assert package.total_shot_duration == 60
    assert max(shot.duration for shot in package.shots) <= 10
    assert [shot.scene_id for shot in package.shots] == [
        "scene_001",
        "scene_002",
        "scene_003",
        "scene_003",
        "scene_004",
        "scene_005",
    ]


def test_preserves_scene_characters_and_prompt_context(
    screenplay: ScreenplayPackage,
) -> None:
    package = RuleShotProvider().generate(screenplay)
    scene_by_id = {scene.scene_id: scene for scene in screenplay.scenes}

    for shot in package.shots:
        scene = scene_by_id[shot.scene_id]
        assert shot.character_ids == scene.characters
        assert shot.image_prompt.strip()
        assert shot.video_prompt.strip()
        assert "竖屏 9:16" in shot.image_prompt
        assert shot.negative_prompt
        assert shot.audio_prompt
        assert shot.keyframe_contract.required_visuals
        assert shot.keyframe_contract.opening_state
        assert shot.keyframe_contract.key_action
        assert shot.keyframe_contract.visible_result


def test_each_scene_duration_is_preserved(screenplay: ScreenplayPackage) -> None:
    package = RuleShotProvider().generate(screenplay)

    for scene in screenplay.scenes:
        total = sum(
            shot.duration for shot in package.shots if shot.scene_id == scene.scene_id
        )
        assert total == scene.duration


def test_generation_is_deterministic(screenplay: ScreenplayPackage) -> None:
    provider = RuleShotProvider()
    assert provider.generate(screenplay) == provider.generate(screenplay)


def test_prompt_requires_non_repeating_action_and_continuity(screenplay: ScreenplayPackage) -> None:
    package = RuleShotProvider(max_shot_duration=6).generate(screenplay)
    assert all("不循环、不重复动作" in shot.video_prompt for shot in package.shots)
    assert all("连续性" in shot.video_prompt for shot in package.shots)


def test_keeps_spoken_text_out_of_visual_prompts() -> None:
    fixture = Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json"
    bundle = StoryMotionBundle.model_validate_json(fixture.read_text(encoding="utf-8"))
    package = RuleShotProvider().generate(bundle.screenplay)
    scenes = {scene.scene_id: scene for scene in bundle.screenplay.scenes}

    for shot in package.shots:
        scene = scenes[shot.scene_id]
        spoken_lines = [
            text
            for text in [
                scene.voiceover,
                *(dialogue.text for dialogue in scene.dialogues),
            ]
            if text
        ]
        visual_text = "\n".join(
            [shot.visual_description, shot.image_prompt, shot.video_prompt]
        )
        for line in spoken_lines:
            assert line not in visual_text
            assert line in shot.audio_prompt


def test_rejects_non_positive_shot_duration() -> None:
    with pytest.raises(ValueError, match="max_shot_duration"):
        RuleShotProvider(max_shot_duration=0)
