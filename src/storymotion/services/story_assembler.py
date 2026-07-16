from __future__ import annotations

from storymotion.models.intermediate import CharacterPackage, PlotPlan, StoryDraft
from storymotion.models.project import ProjectBrief
from storymotion.models.story import StoryPackage, Worldview


def assemble_story_package(
    *,
    brief: ProjectBrief,
    worldview: Worldview,
    characters: CharacterPackage,
    plot: PlotPlan,
    draft: StoryDraft,
) -> StoryPackage:
    if plot.target_duration != brief.target_duration:
        raise ValueError(
            "plot target_duration does not match ProjectBrief: "
            f"{plot.target_duration} != {brief.target_duration}"
        )
    if len(characters.characters) > brief.max_characters:
        raise ValueError(
            "character limit exceeded: "
            f"{len(characters.characters)} > {brief.max_characters}"
        )
    if len(worldview.locations) > brief.max_locations:
        raise ValueError(
            "location limit exceeded: "
            f"{len(worldview.locations)} > {brief.max_locations}"
        )
    if brief.protagonist_name not in {
        character.name for character in characters.characters
    }:
        raise ValueError("ProjectBrief protagonist is missing from character package")

    return StoryPackage(
        title=draft.title,
        logline=draft.logline,
        target_duration=brief.target_duration,
        worldview=worldview,
        characters=characters.characters,
        beats=plot.beats,
        story_text=draft.story_text,
    )

