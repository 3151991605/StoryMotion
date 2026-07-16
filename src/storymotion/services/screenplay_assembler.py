from __future__ import annotations

from storymotion.models.intermediate import ScenePackage
from storymotion.models.screenplay import ScreenplayPackage
from storymotion.models.story import StoryPackage


def assemble_screenplay_package(
    *,
    story: StoryPackage,
    scene_package: ScenePackage,
) -> ScreenplayPackage:
    if scene_package.target_duration != story.target_duration:
        raise ValueError(
            "scene target_duration does not match StoryPackage: "
            f"{scene_package.target_duration} != {story.target_duration}"
        )
    return ScreenplayPackage(
        title=story.title,
        target_duration=story.target_duration,
        characters=story.characters,
        locations=story.worldview.locations,
        scenes=scene_package.scenes,
    )
