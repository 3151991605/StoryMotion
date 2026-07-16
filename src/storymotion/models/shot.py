from __future__ import annotations

from pydantic import Field, model_validator

from .base import CharacterId, SceneId, ShotId, StrictModel, duplicate_values


class Shot(StrictModel):
    shot_id: ShotId
    scene_id: SceneId
    duration: float = Field(gt=0, le=60)
    shot_type: str = Field(min_length=1, max_length=100)
    camera_movement: str = Field(min_length=1, max_length=200)
    visual_description: str = Field(min_length=1, max_length=3000)
    character_ids: list[CharacterId] = Field(default_factory=list, max_length=6)
    image_prompt: str = Field(min_length=1, max_length=5000)
    video_prompt: str = Field(min_length=1, max_length=5000)
    negative_prompt: str | None = Field(default=None, max_length=3000)
    audio_prompt: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="after")
    def validate_character_ids(self) -> "Shot":
        duplicates = duplicate_values(self.character_ids)
        if duplicates:
            raise ValueError(f"duplicate shot character IDs: {sorted(duplicates)}")
        return self


class ShotPackage(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    target_duration: int = Field(ge=15, le=180)
    shots: list[Shot] = Field(min_length=1, max_length=60)

    @property
    def total_shot_duration(self) -> float:
        return sum(shot.duration for shot in self.shots)

    @model_validator(mode="after")
    def validate_storyboard(self) -> "ShotPackage":
        duplicates = duplicate_values(shot.shot_id for shot in self.shots)
        if duplicates:
            raise ValueError(f"duplicate shot IDs: {sorted(duplicates)}")
        if abs(self.total_shot_duration - self.target_duration) > 0.01:
            raise ValueError(
                "shot duration must equal target_duration: "
                f"{self.total_shot_duration} != {self.target_duration}"
            )
        return self
