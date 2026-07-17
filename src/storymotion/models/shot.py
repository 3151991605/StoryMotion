from __future__ import annotations

from pydantic import Field, model_validator

from .base import CharacterId, SceneId, ShotId, StrictModel, duplicate_values


class KeyframeContract(StrictModel):
    """Observable requirements a generated keyframe must satisfy."""

    required_visuals: list[str] = Field(min_length=1, max_length=8)
    opening_state: str = Field(min_length=1, max_length=1000)
    key_action: str = Field(min_length=1, max_length=1000)
    visible_result: str = Field(min_length=1, max_length=1000)
    continuity_anchor: str = Field(min_length=1, max_length=1500)


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
    keyframe_contract: KeyframeContract
    negative_prompt: str | None = Field(default=None, max_length=3000)
    audio_prompt: str | None = Field(default=None, max_length=3000)

    @model_validator(mode="before")
    @classmethod
    def add_legacy_keyframe_contract(cls, value):
        """Keep persisted storyboards readable while new providers fill this explicitly."""
        if not isinstance(value, dict) or value.get("keyframe_contract") is not None:
            return value
        description = str(value.get("visual_description") or "关键画面")
        copied = dict(value)
        copied["keyframe_contract"] = {
            "required_visuals": [description],
            "opening_state": description,
            "key_action": description,
            "visible_result": description,
            "continuity_anchor": "保持人物、服装、场景和光线的一致性。",
        }
        return copied

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
