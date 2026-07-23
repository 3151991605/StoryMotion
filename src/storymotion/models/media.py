from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .base import StrictModel


AspectRatio = Literal["1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16", "21:9"]
VideoResolution = Literal["720P", "768P", "1080P"]


class MediaTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ImageGenerationRequest(StrictModel):
    prompt: str = Field(min_length=1, max_length=1500)
    aspect_ratio: AspectRatio = "9:16"
    reference_image: str | None = Field(default=None, min_length=1, max_length=30_000_000)
    reference_images: list[str] = Field(default_factory=list, max_length=9)
    seed: int | None = Field(default=None, ge=0)

    @field_validator("reference_images")
    @classmethod
    def validate_reference_images(cls, values: list[str]) -> list[str]:
        if any(not isinstance(value, str) or not value or len(value) > 30_000_000 for value in values):
            raise ValueError("reference images must be non-empty strings of at most 30 MB")
        return values

    @model_validator(mode="after")
    def validate_total_reference_count(self) -> "ImageGenerationRequest":
        total = len(self.reference_images) + int(self.reference_image is not None)
        if total > 9:
            raise ValueError("image generation supports at most 9 reference images")
        return self


class GeneratedImage(StrictModel):
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    request_id: str = Field(min_length=1, max_length=200)
    path: Path
    media_type: Literal["image/jpeg", "image/png", "image/webp"]


class VideoGenerationRequest(StrictModel):
    prompt: str = Field(min_length=1, max_length=5000)
    duration: Literal[6, 10] = 6
    resolution: VideoResolution = "768P"
    first_frame_image: str | None = Field(
        default=None, min_length=1, max_length=30_000_000
    )

    @model_validator(mode="after")
    def validate_duration_resolution(self) -> "VideoGenerationRequest":
        if self.resolution == "1080P" and self.duration != 6:
            raise ValueError("1080P video generation supports duration 6 only")
        return self


class VideoTask(StrictModel):
    provider: str = Field(min_length=1, max_length=100)
    task_id: str = Field(min_length=1, max_length=200)
    status: MediaTaskStatus
    file_id: str | None = Field(default=None, min_length=1, max_length=200)
    error: str | None = Field(default=None, min_length=1, max_length=2000)
    width: int | None = Field(default=None, gt=0, le=8192)
    height: int | None = Field(default=None, gt=0, le=8192)

    @model_validator(mode="after")
    def validate_terminal_state(self) -> "VideoTask":
        if self.status is MediaTaskStatus.SUCCEEDED and self.file_id is None:
            raise ValueError("succeeded video task requires file_id")
        if self.status is MediaTaskStatus.FAILED and self.error is None:
            raise ValueError("failed video task requires error")
        return self


class VideoResult(StrictModel):
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    task_id: str = Field(min_length=1, max_length=200)
    file_id: str = Field(min_length=1, max_length=200)
    download_url: str = Field(min_length=1, max_length=4000)
    bytes: int | None = Field(default=None, ge=0, le=1_000_000_000)

    @field_validator("download_url")
    @classmethod
    def validate_download_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("download_url must use https")
        return value
