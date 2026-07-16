from __future__ import annotations

from pathlib import Path
from typing import Protocol

from storymotion.models.media import (
    GeneratedImage,
    ImageGenerationRequest,
    VideoGenerationRequest,
    VideoResult,
    VideoTask,
)


class ImageProvider(Protocol):
    def generate(
        self, request: ImageGenerationRequest, *, output_file: Path
    ) -> GeneratedImage: ...


class VideoProvider(Protocol):
    def submit(self, request: VideoGenerationRequest) -> VideoTask: ...

    def get_status(self, task_id: str) -> VideoTask: ...

    def get_result(self, task_id: str) -> VideoResult: ...

    def download(self, result: VideoResult, output_file: Path) -> Path: ...
