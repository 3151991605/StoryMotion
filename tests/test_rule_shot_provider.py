from __future__ import annotations

from pathlib import Path

import pytest

from storymotion.models import ScreenplayPackage
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
        assert "vertical 9:16" in shot.image_prompt
        assert shot.negative_prompt
        assert shot.audio_prompt


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


def test_rejects_non_positive_shot_duration() -> None:
    with pytest.raises(ValueError, match="max_shot_duration"):
        RuleShotProvider(max_shot_duration=0)
