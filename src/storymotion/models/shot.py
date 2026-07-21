from __future__ import annotations

from pydantic import Field, model_validator

from .base import CharacterId, SceneId, ShotId, StrictModel, duplicate_values


class KeyframeContract(StrictModel):
    """The complete visual-only contract for a generated shot.

    Dialogue and narration remain on :class:`Shot`; a media prompt is always
    rebuilt from this contract at the provider boundary.
    """

    character_appearances: list[str] = Field(min_length=1, max_length=8)
    start_keyframe: str = Field(min_length=1, max_length=1000)
    action: str = Field(min_length=1, max_length=1000)
    result: str = Field(min_length=1, max_length=1000)
    transition_from_previous: str = Field(min_length=1, max_length=1500)
    transition_to_next: str = Field(min_length=1, max_length=1500)

    @model_validator(mode="before")
    @classmethod
    def upgrade_v1_contract(cls, value):
        """Read persisted five-field contracts without rewriting old bundles."""
        if not isinstance(value, dict) or "character_appearances" in value:
            return value
        copied = dict(value)
        continuity = str(
            copied.pop("continuity_anchor", "保持人物、服装、场景和光线一致。")
        )
        copied["character_appearances"] = copied.pop("required_visuals", [])
        copied["start_keyframe"] = copied.pop("opening_state", "")
        copied["action"] = copied.pop("key_action", "")
        copied["result"] = copied.pop("visible_result", "")
        copied["transition_from_previous"] = continuity
        copied["transition_to_next"] = continuity
        return copied

    # Compatibility aliases keep all current prompt and reference services
    # working with saved bundles generated before the contract expansion.
    @property
    def required_visuals(self) -> list[str]:
        return self.character_appearances

    @property
    def opening_state(self) -> str:
        return self.start_keyframe

    @property
    def key_action(self) -> str:
        return self.action

    @property
    def visible_result(self) -> str:
        return self.result

    @property
    def continuity_anchor(self) -> str:
        return self.transition_to_next


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
