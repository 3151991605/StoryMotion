from __future__ import annotations

from collections import defaultdict

from pydantic import model_validator

from .base import StrictModel
from .project import ProjectBrief
from .screenplay import ScreenplayPackage
from .shot import ShotPackage
from .story import StoryPackage


class StoryMotionBundle(StrictModel):
    """A complete contract fixture used for cross-layer integration checks."""

    brief: ProjectBrief
    story: StoryPackage
    screenplay: ScreenplayPackage
    storyboard: ShotPackage

    @model_validator(mode="after")
    def validate_cross_layer_contract(self) -> "StoryMotionBundle":
        durations = {
            self.brief.target_duration,
            self.story.target_duration,
            self.screenplay.target_duration,
            self.storyboard.target_duration,
        }
        if len(durations) != 1:
            raise ValueError("target_duration must match across all protocol layers")

        story_characters = {character.id: character for character in self.story.characters}
        screenplay_characters = {
            character.id: character for character in self.screenplay.characters
        }
        if set(story_characters) != set(screenplay_characters):
            raise ValueError("character ID sets must match between story and screenplay")
        for character_id, character in story_characters.items():
            if character != screenplay_characters[character_id]:
                raise ValueError(f"character definition drift for {character_id}")

        if self.brief.protagonist_name not in {
            character.name for character in self.story.characters
        }:
            raise ValueError("brief protagonist is missing from StoryPackage")
        if len(self.story.characters) > self.brief.max_characters:
            raise ValueError(
                "character limit exceeded: "
                f"{len(self.story.characters)} > {self.brief.max_characters}"
            )

        story_locations = {
            location.id: location for location in self.story.worldview.locations
        }
        screenplay_locations = {
            location.id: location for location in self.screenplay.locations
        }
        if set(story_locations) != set(screenplay_locations):
            raise ValueError("location ID sets must match between story and screenplay")
        for location_id, location in story_locations.items():
            if location != screenplay_locations[location_id]:
                raise ValueError(f"location definition drift for {location_id}")
        story_props = {prop.id: prop for prop in self.story.props}
        screenplay_props = {prop.id: prop for prop in self.screenplay.props}
        if set(story_props) != set(screenplay_props):
            raise ValueError("prop ID sets must match between story and screenplay")
        for prop_id, prop in story_props.items():
            if prop != screenplay_props[prop_id]:
                raise ValueError(f"prop definition drift for {prop_id}")
        if len(story_locations) > self.brief.max_locations:
            raise ValueError(
                "location limit exceeded: "
                f"{len(story_locations)} > {self.brief.max_locations}"
            )

        screenplay_scene_ids = {
            scene.scene_id for scene in self.screenplay.scenes
        }
        screenplay_character_ids = set(screenplay_characters)
        screenplay_prop_ids = set(screenplay_props)
        shot_duration_by_scene: dict[str, float] = defaultdict(float)
        for shot in self.storyboard.shots:
            if shot.scene_id not in screenplay_scene_ids:
                raise ValueError(
                    f"shot {shot.shot_id} references unknown screenplay scene "
                    f"{shot.scene_id}"
                )
            unknown_characters = set(shot.character_ids) - screenplay_character_ids
            if unknown_characters:
                raise ValueError(
                    f"shot {shot.shot_id} references unknown character IDs: "
                    f"{sorted(unknown_characters)}"
                )
            unknown_props = set(shot.prop_ids) - screenplay_prop_ids
            if unknown_props:
                raise ValueError(
                    f"shot {shot.shot_id} references unknown prop IDs: "
                    f"{sorted(unknown_props)}"
                )
            shot_duration_by_scene[shot.scene_id] += shot.duration

        for scene in self.screenplay.scenes:
            shot_duration = shot_duration_by_scene.get(scene.scene_id, 0.0)
            if abs(shot_duration - scene.duration) > 0.01:
                raise ValueError(
                    f"shot duration for {scene.scene_id} must equal scene duration: "
                    f"{shot_duration} != {scene.duration}"
                )
        return self
