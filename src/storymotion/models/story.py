from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .base import CharacterId, LocationId, PropId, StrictModel, duplicate_values


CANONICAL_BEAT_ORDER = (
    "hook",
    "setup",
    "conflict",
    "reversal",
    "cliffhanger",
)


class Appearance(StrictModel):
    hair: str = Field(min_length=1, max_length=200)
    clothing: str = Field(min_length=1, max_length=300)
    distinctive_features: list[str] = Field(default_factory=list, max_length=5)


class Character(StrictModel):
    id: CharacterId
    name: str = Field(min_length=1, max_length=80)
    role: str = Field(min_length=1, max_length=80)
    age: int | None = Field(default=None, ge=0, le=200)
    personality: list[str] = Field(min_length=1, max_length=8)
    goal: str = Field(min_length=1, max_length=500)
    ability: str | None = Field(default=None, max_length=500)
    appearance: Appearance
    visual_prompt_zh: str = Field(min_length=1, max_length=2000)
    visual_prompt_en: str = Field(min_length=1, max_length=2000)


class Location(StrictModel):
    id: LocationId
    name: str = Field(min_length=1, max_length=120)
    visual_description: str = Field(min_length=1, max_length=1000)


class StoryProp(StrictModel):
    """A plot-bearing object whose design must remain fixed across shots."""

    id: PropId
    name: str = Field(min_length=1, max_length=120)
    visual_description: str = Field(min_length=1, max_length=1000)
    continuity_features: list[str] = Field(default_factory=list, max_length=8)
    aliases: list[str] = Field(default_factory=list, max_length=8)


class Worldview(StrictModel):
    world_name: str = Field(min_length=1, max_length=120)
    era: str = Field(min_length=1, max_length=200)
    power_system: str = Field(min_length=1, max_length=500)
    special_rule: str = Field(min_length=1, max_length=1000)
    locations: list[Location] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def validate_location_ids(self) -> "Worldview":
        duplicates = duplicate_values(location.id for location in self.locations)
        if duplicates:
            raise ValueError(f"duplicate location IDs: {sorted(duplicates)}")
        return self


class PlotBeat(StrictModel):
    beat_type: Literal["hook", "setup", "conflict", "reversal", "cliffhanger"]
    duration: int = Field(gt=0, le=180)
    content: str = Field(min_length=1, max_length=1000)


def validate_plot_beats(beats: list[PlotBeat], target_duration: int) -> None:
    total_duration = sum(beat.duration for beat in beats)
    if total_duration != target_duration:
        raise ValueError(
            "plot beat duration must equal target_duration: "
            f"{total_duration} != {target_duration}"
        )
    actual_order = tuple(beat.beat_type for beat in beats)
    if actual_order != CANONICAL_BEAT_ORDER:
        raise ValueError(
            "plot beats must follow canonical order: "
            f"{list(CANONICAL_BEAT_ORDER)}; got {list(actual_order)}"
        )


class StoryPackage(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    logline: str = Field(min_length=1, max_length=1000)
    target_duration: int = Field(ge=15, le=180)
    worldview: Worldview
    characters: list[Character] = Field(min_length=1, max_length=6)
    props: list[StoryProp] = Field(default_factory=list, max_length=8)
    beats: list[PlotBeat] = Field(min_length=1, max_length=10)
    story_text: str = Field(min_length=1, max_length=10000)

    @property
    def total_beat_duration(self) -> int:
        return sum(beat.duration for beat in self.beats)

    @model_validator(mode="after")
    def validate_story(self) -> "StoryPackage":
        duplicate_ids = duplicate_values(character.id for character in self.characters)
        if duplicate_ids:
            raise ValueError(f"duplicate character IDs: {sorted(duplicate_ids)}")
        duplicate_names = duplicate_values(character.name for character in self.characters)
        if duplicate_names:
            raise ValueError(f"duplicate character names: {sorted(duplicate_names)}")
        duplicate_prop_ids = duplicate_values(prop.id for prop in self.props)
        if duplicate_prop_ids:
            raise ValueError(f"duplicate prop IDs: {sorted(duplicate_prop_ids)}")
        duplicate_prop_names = duplicate_values(prop.name for prop in self.props)
        if duplicate_prop_names:
            raise ValueError(f"duplicate prop names: {sorted(duplicate_prop_names)}")
        validate_plot_beats(self.beats, self.target_duration)
        return self
