from __future__ import annotations

from typing import Annotated, Iterable

from pydantic import BaseModel, ConfigDict, Field


CharacterId = Annotated[str, Field(pattern=r"^char_[A-Za-z0-9_-]+$")]
LocationId = Annotated[str, Field(pattern=r"^loc_[A-Za-z0-9_-]+$")]
SceneId = Annotated[str, Field(pattern=r"^scene_[A-Za-z0-9_-]+$")]
ShotId = Annotated[str, Field(pattern=r"^shot_[A-Za-z0-9_-]+$")]


class StrictModel(BaseModel):
    """Base class for canonical protocol objects."""

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        str_strip_whitespace=True,
        validate_assignment=True,
    )


def duplicate_values(values: Iterable[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates
