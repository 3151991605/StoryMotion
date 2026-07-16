from __future__ import annotations

from pydantic import Field, model_validator

from .base import StrictModel, duplicate_values
from .screenplay import Scene
from .story import Character, PlotBeat, validate_plot_beats


class CharacterPackage(StrictModel):
    characters: list[Character] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def validate_characters(self) -> "CharacterPackage":
        duplicate_ids = duplicate_values(character.id for character in self.characters)
        if duplicate_ids:
            raise ValueError(f"duplicate character IDs: {sorted(duplicate_ids)}")
        duplicate_names = duplicate_values(
            character.name for character in self.characters
        )
        if duplicate_names:
            raise ValueError(f"duplicate character names: {sorted(duplicate_names)}")
        return self


class PlotPlan(StrictModel):
    target_duration: int = Field(ge=15, le=180)
    beats: list[PlotBeat] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_plan(self) -> "PlotPlan":
        validate_plot_beats(self.beats, self.target_duration)
        return self


class StoryDraft(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    logline: str = Field(min_length=1, max_length=1000)
    story_text: str = Field(min_length=500, max_length=1000)


class ScenePackage(StrictModel):
    target_duration: int = Field(ge=15, le=180)
    scenes: list[Scene] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def validate_scenes(self) -> "ScenePackage":
        duplicate_ids = duplicate_values(scene.scene_id for scene in self.scenes)
        if duplicate_ids:
            raise ValueError(f"duplicate scene IDs: {sorted(duplicate_ids)}")
        total_duration = sum(scene.duration for scene in self.scenes)
        if total_duration != self.target_duration:
            raise ValueError(
                "scene duration must equal target_duration: "
                f"{total_duration} != {self.target_duration}"
            )
        return self
