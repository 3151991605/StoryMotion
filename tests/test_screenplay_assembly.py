from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from storymotion.models import ScenePackage, StoryMotionBundle
from storymotion.services import assemble_screenplay_package


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json"


@pytest.fixture
def bundle() -> StoryMotionBundle:
    return StoryMotionBundle.model_validate_json(
        FIXTURE_PATH.read_text(encoding="utf-8")
    )


def make_scene_package(bundle: StoryMotionBundle) -> ScenePackage:
    return ScenePackage(
        target_duration=bundle.screenplay.target_duration,
        scenes=bundle.screenplay.scenes,
    )


def test_scene_package_requires_exact_total_duration(
    bundle: StoryMotionBundle,
) -> None:
    scenes = [scene.model_dump() for scene in bundle.screenplay.scenes]
    scenes[0]["duration"] = 29
    with pytest.raises(ValidationError, match="scene duration"):
        ScenePackage(target_duration=60, scenes=scenes)


def test_scene_package_rejects_duplicate_scene_ids(
    bundle: StoryMotionBundle,
) -> None:
    duplicate = [bundle.screenplay.scenes[0], bundle.screenplay.scenes[0]]
    with pytest.raises(ValidationError, match="duplicate scene IDs"):
        ScenePackage(target_duration=60, scenes=duplicate)


def test_assembles_screenplay_with_canonical_story_definitions(
    bundle: StoryMotionBundle,
) -> None:
    screenplay = assemble_screenplay_package(
        story=bundle.story,
        scene_package=make_scene_package(bundle),
    )

    assert screenplay.title == bundle.story.title
    assert screenplay.target_duration == bundle.story.target_duration
    assert screenplay.characters == bundle.story.characters
    assert screenplay.locations == bundle.story.worldview.locations
    assert screenplay.scenes == bundle.screenplay.scenes
    assert screenplay.total_scene_duration == 60
