from pathlib import Path

import pytest
from pydantic import ValidationError

from storymotion.models import (
    GeneratedImage,
    ImageGenerationRequest,
    MediaTaskStatus,
    VideoGenerationRequest,
    VideoResult,
    VideoTask,
)


def test_image_request_is_bounded_for_vertical_first_frame() -> None:
    request = ImageGenerationRequest(prompt="cinematic frame", aspect_ratio="9:16")

    assert request.aspect_ratio == "9:16"
    with pytest.raises(ValidationError):
        ImageGenerationRequest(prompt="x" * 1501)


def test_video_request_rejects_unsupported_duration_resolution_pair() -> None:
    with pytest.raises(ValidationError, match="1080P.*6"):
        VideoGenerationRequest(
            prompt="camera pushes in",
            duration=10,
            resolution="1080P",
        )


def test_terminal_video_task_requires_matching_payload() -> None:
    with pytest.raises(ValidationError, match="file_id"):
        VideoTask(
            provider="minimax-hailuo",
            task_id="task-1",
            status=MediaTaskStatus.SUCCEEDED,
        )
    with pytest.raises(ValidationError, match="error"):
        VideoTask(
            provider="minimax-hailuo",
            task_id="task-1",
            status=MediaTaskStatus.FAILED,
        )


def test_artifacts_use_local_paths_and_https_results(tmp_path: Path) -> None:
    image = GeneratedImage(
        provider="minimax",
        model="image-01",
        request_id="image-1",
        path=tmp_path / "frame.jpg",
        media_type="image/jpeg",
    )
    result = VideoResult(
        provider="minimax-hailuo",
        model="MiniMax-Hailuo-2.3",
        task_id="task-1",
        file_id="file-1",
        download_url="https://filecdn.minimax.chat/output.mp4",
    )

    assert image.path.name == "frame.jpg"
    assert result.download_url.startswith("https://")

