from __future__ import annotations

from pydantic import Field, model_validator

from .base import StrictModel, duplicate_values


class ProjectBrief(StrictModel):
    genre: str = Field(min_length=1, max_length=80)
    style: list[str] = Field(min_length=1, max_length=5)
    protagonist_name: str = Field(min_length=1, max_length=80)
    core_idea: str = Field(min_length=1, max_length=1000)
    target_duration: int = Field(default=60, ge=15, le=180)
    max_characters: int = Field(default=3, ge=1, le=6)
    max_locations: int = Field(default=5, ge=1, le=10)
    ending_type: str = Field(default="cliffhanger", min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_styles(self) -> "ProjectBrief":
        if any(not style for style in self.style):
            raise ValueError("style entries must be non-empty")
        duplicates = duplicate_values(self.style)
        if duplicates:
            raise ValueError(f"duplicate styles are not allowed: {sorted(duplicates)}")
        return self

