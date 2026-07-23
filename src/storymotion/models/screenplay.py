from __future__ import annotations

from pydantic import Field, model_validator

from .base import CharacterId, LocationId, PropId, SceneId, StrictModel, duplicate_values
from .story import Character, Location, StoryProp


class Dialogue(StrictModel):
    speaker_id: CharacterId
    text: str = Field(min_length=1, max_length=500)
    emotion: str | None = Field(default=None, max_length=100)


class Scene(StrictModel):
    scene_id: SceneId
    location_id: LocationId
    duration: int = Field(gt=0, le=180)
    characters: list[CharacterId] = Field(default_factory=list, max_length=6)
    prop_ids: list[PropId] = Field(default_factory=list, max_length=8)
    scene_goal: str = Field(min_length=1, max_length=500)
    action: str = Field(min_length=1, max_length=3000)
    dialogues: list[Dialogue] = Field(default_factory=list, max_length=20)
    voiceover: str | None = Field(default=None, max_length=1500)
    emotion: str = Field(min_length=1, max_length=100)
    transition: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_scene_characters(self) -> "Scene":
        duplicates = duplicate_values(self.characters)
        if duplicates:
            raise ValueError(f"duplicate scene character IDs: {sorted(duplicates)}")
        duplicate_props = duplicate_values(self.prop_ids)
        if duplicate_props:
            raise ValueError(f"duplicate scene prop IDs: {sorted(duplicate_props)}")
        scene_characters = set(self.characters)
        for dialogue in self.dialogues:
            if dialogue.speaker_id not in scene_characters:
                raise ValueError(
                    f"dialogue speaker {dialogue.speaker_id} is not present in scene"
                )
        return self


class ScreenplayPackage(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    target_duration: int = Field(ge=15, le=180)
    characters: list[Character] = Field(min_length=1, max_length=6)
    locations: list[Location] = Field(min_length=1, max_length=10)
    props: list[StoryProp] = Field(default_factory=list, max_length=8)
    scenes: list[Scene] = Field(min_length=1, max_length=30)

    @property
    def total_scene_duration(self) -> int:
        return sum(scene.duration for scene in self.scenes)

    @model_validator(mode="after")
    def validate_screenplay(self) -> "ScreenplayPackage":
        for label, values in (
            ("character", [character.id for character in self.characters]),
            ("location", [location.id for location in self.locations]),
            ("prop", [prop.id for prop in self.props]),
            ("scene", [scene.scene_id for scene in self.scenes]),
        ):
            duplicates = duplicate_values(values)
            if duplicates:
                raise ValueError(f"duplicate {label} IDs: {sorted(duplicates)}")

        character_ids = {character.id for character in self.characters}
        location_ids = {location.id for location in self.locations}
        prop_ids = {prop.id for prop in self.props}
        for scene in self.scenes:
            if scene.location_id not in location_ids:
                raise ValueError(
                    f"scene {scene.scene_id} references unknown location {scene.location_id}"
                )
            unknown_characters = set(scene.characters) - character_ids
            if unknown_characters:
                raise ValueError(
                    f"scene {scene.scene_id} references unknown character IDs: "
                    f"{sorted(unknown_characters)}"
                )
            unknown_props = set(scene.prop_ids) - prop_ids
            if unknown_props:
                raise ValueError(
                    f"scene {scene.scene_id} references unknown prop IDs: "
                    f"{sorted(unknown_props)}"
                )

        if self.total_scene_duration != self.target_duration:
            raise ValueError(
                "scene duration must equal target_duration: "
                f"{self.total_scene_duration} != {self.target_duration}"
            )
        return self
