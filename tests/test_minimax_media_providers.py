from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest

from storymotion.models import (
    ImageGenerationRequest,
    MediaTaskStatus,
    VideoGenerationRequest,
)
from storymotion.providers.minimax_media import (
    HailuoVideoProvider,
    MiniMaxAccountError,
    MiniMaxImageProvider,
    MiniMaxMediaProtocolError,
)


class ScriptedTransport:
    def __init__(self, responses: list[dict[str, Any] | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[
            tuple[str, str, dict[str, Any] | None, dict[str, str] | None, float]
        ] = []
        self.downloads: list[tuple[str, Path, float, int]] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None,
        params: dict[str, str] | None,
        timeout: float,
    ) -> dict[str, Any]:
        self.calls.append((method, path, payload, params, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def download(
        self,
        url: str,
        output_file: Path,
        *,
        timeout: float,
        max_bytes: int,
    ) -> Path:
        self.downloads.append((url, output_file, timeout, max_bytes))
        return output_file


def success_base() -> dict[str, Any]:
    return {"base_resp": {"status_code": 0, "status_msg": "success"}}


def test_image_provider_writes_one_valid_base64_image(tmp_path: Path) -> None:
    jpeg = b"\xff\xd8\xff\xe0" + b"image-bytes"
    transport = ScriptedTransport(
        [
            {
                "id": "image-1",
                "data": {"image_base64": [base64.b64encode(jpeg).decode()]},
                **success_base(),
            }
        ]
    )
    provider = MiniMaxImageProvider(transport)
    output = tmp_path / "shot_001.jpg"

    artifact = provider.generate(
        ImageGenerationRequest(prompt="vertical cinematic frame"),
        output_file=output,
    )

    assert output.read_bytes() == jpeg
    assert artifact.path == output
    assert artifact.media_type == "image/jpeg"
    assert len(transport.calls) == 1
    method, path, payload, params, _ = transport.calls[0]
    assert (method, path, params) == ("POST", "/v1/image_generation", None)
    assert payload == {
        "model": "image-01",
        "prompt": "vertical cinematic frame",
        "aspect_ratio": "9:16",
        "response_format": "base64",
        "n": 1,
        "prompt_optimizer": False,
        "aigc_watermark": False,
    }


def test_image_provider_rejects_non_image_without_retry(tmp_path: Path) -> None:
    transport = ScriptedTransport(
        [
            {
                "id": "image-1",
                "data": {
                    "image_base64": [base64.b64encode(b"not-image").decode()]
                },
                **success_base(),
            }
        ]
    )

    with pytest.raises(MiniMaxMediaProtocolError, match="image format"):
        MiniMaxImageProvider(transport).generate(
            ImageGenerationRequest(prompt="frame"),
            output_file=tmp_path / "frame.jpg",
        )

    assert len(transport.calls) == 1
    assert not (tmp_path / "frame.jpg").exists()


def test_hailuo_submit_image_to_video_payload_is_exact() -> None:
    transport = ScriptedTransport([{"task_id": "task-1", **success_base()}])
    provider = HailuoVideoProvider(transport)

    task = provider.submit(
        VideoGenerationRequest(
            prompt="slow push in",
            first_frame_image="data:image/jpeg;base64,AAAA",
        )
    )

    assert task.status is MediaTaskStatus.PENDING
    assert task.task_id == "task-1"
    assert len(transport.calls) == 1
    payload = transport.calls[0][2]
    assert payload == {
        "model": "MiniMax-Hailuo-2.3",
        "prompt": "slow push in",
        "duration": 6,
        "resolution": "768P",
        "aigc_watermark": False,
        "first_frame_image": "data:image/jpeg;base64,AAAA",
    }


@pytest.mark.parametrize(
    ("remote", "expected"),
    [
        ("Preparing", MediaTaskStatus.PENDING),
        ("Queueing", MediaTaskStatus.PENDING),
        ("Processing", MediaTaskStatus.RUNNING),
    ],
)
def test_hailuo_maps_nonterminal_statuses(
    remote: str, expected: MediaTaskStatus
) -> None:
    transport = ScriptedTransport(
        [{"task_id": "task-1", "status": remote, **success_base()}]
    )

    task = HailuoVideoProvider(transport).get_status("task-1")

    assert task.status is expected
    assert transport.calls[0][3] == {"task_id": "task-1"}


def test_hailuo_success_gets_file_metadata_and_downloads(tmp_path: Path) -> None:
    transport = ScriptedTransport(
        [
            {
                "task_id": "task-1",
                "status": "Success",
                "file_id": "file-1",
                "video_width": 768,
                "video_height": 1366,
                **success_base(),
            },
            {
                "file": {
                    "file_id": "file-1",
                    "bytes": 1234,
                    "download_url": "https://filecdn.minimax.chat/output.mp4",
                },
                **success_base(),
            },
        ]
    )
    provider = HailuoVideoProvider(transport)

    result = provider.get_result("task-1")
    output = provider.download(result, tmp_path / "shot_001.mp4")

    assert result.file_id == "file-1"
    assert result.download_url.endswith("output.mp4")
    assert transport.calls[1][0:2] == ("GET", "/v1/files/retrieve")
    assert transport.calls[1][3] == {"file_id": "file-1"}
    assert output == tmp_path / "shot_001.mp4"
    assert len(transport.downloads) == 1


def test_hailuo_failed_task_is_normalized() -> None:
    transport = ScriptedTransport(
        [
            {
                "task_id": "task-1",
                "status": "Fail",
                "error_message": "content rejected",
                **success_base(),
            }
        ]
    )

    task = HailuoVideoProvider(transport).get_status("task-1")

    assert task.status is MediaTaskStatus.FAILED
    assert task.error == "content rejected"


def test_hailuo_success_without_file_id_is_protocol_error() -> None:
    transport = ScriptedTransport(
        [{"task_id": "task-1", "status": "Success", **success_base()}]
    )

    with pytest.raises(MiniMaxMediaProtocolError, match="task payload"):
        HailuoVideoProvider(transport).get_status("task-1")


def test_hailuo_normalizes_numeric_file_id_on_success() -> None:
    transport = ScriptedTransport(
        [
            {
                "task_id": "task-1",
                "status": "Success",
                "file_id": 123456,
                "video_width": 768,
                "video_height": 1366,
                **success_base(),
            }
        ]
    )

    task = HailuoVideoProvider(transport).get_status("task-1")

    assert task.file_id == "123456"


def test_hailuo_ignores_zero_dimensions_before_completion() -> None:
    transport = ScriptedTransport(
        [
            {
                "task_id": "task-1",
                "status": "Processing",
                "video_width": 0,
                "video_height": 0,
                **success_base(),
            }
        ]
    )

    task = HailuoVideoProvider(transport).get_status("task-1")

    assert task.status is MediaTaskStatus.RUNNING
    assert task.width is None
    assert task.height is None


def test_hailuo_account_error_is_classified_without_retry() -> None:
    transport = ScriptedTransport(
        [
            {
                "base_resp": {
                    "status_code": 2056,
                    "status_msg": "insufficient quota",
                }
            }
        ]
    )

    with pytest.raises(MiniMaxAccountError, match="2056"):
        HailuoVideoProvider(transport).submit(
            VideoGenerationRequest(prompt="slow push in")
        )

    assert len(transport.calls) == 1
