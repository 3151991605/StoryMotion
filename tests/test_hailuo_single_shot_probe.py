from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from storymotion.models import ShotPackage
from storymotion.providers import MiniMaxAccountError


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import verify_hailuo_single_shot as probe  # noqa: E402


PACKAGE_FILE = ROOT / "outputs/verification/minimax_shot_provider_package.json"


def load_package() -> ShotPackage:
    return ShotPackage.model_validate_json(PACKAGE_FILE.read_text(encoding="utf-8"))


def test_dry_run_prepares_only_one_six_second_vertical_shot() -> None:
    summary = probe.build_dry_run_summary(load_package(), shot_id="shot_001")

    assert summary["mode"] == "dry-run"
    assert summary["network_requests"] == 0
    assert summary["shot_id"] == "shot_001"
    assert summary["image_request"]["model"] == "image-01"
    assert summary["image_request"]["aspect_ratio"] == "9:16"
    assert summary["video_request"]["model"] == "MiniMax-Hailuo-2.3"
    assert summary["video_request"]["duration"] == 6
    assert summary["video_request"]["resolution"] == "768P"
    assert summary["video_request"]["first_frame_source"] == "generated-image"


def test_dry_run_rejects_unknown_shot() -> None:
    try:
        probe.build_dry_run_summary(load_package(), shot_id="shot_999")
    except ValueError as exc:
        assert "shot_999" in str(exc)
    else:
        raise AssertionError("unknown shot ID should fail")


def test_image_data_url_is_bounded_and_typed(tmp_path: Path) -> None:
    image = tmp_path / "frame.jpg"
    image.write_bytes(b"\xff\xd8\xff\xe0image")

    value = probe.image_to_data_url(image, max_bytes=100)

    assert value.startswith("data:image/jpeg;base64,")


def test_video_key_is_required_and_kept_separate_from_llm_key() -> None:
    environment = {
        "MINIMAX_API_KEY": "llm-key",
        "MINIMAX_VIDEO_API_KEY": "video-key",
    }

    assert probe.get_video_api_key(environment) == "video-key"
    with pytest.raises(ValueError, match="MINIMAX_VIDEO_API_KEY"):
        probe.get_video_api_key({"MINIMAX_API_KEY": "llm-key"})


class RejectingVideoTransport:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None,
        params: dict[str, str] | None,
        timeout: float,
    ) -> dict[str, Any]:
        self.calls.append(path)
        return {
            "base_resp": {
                "status_code": 2056,
                "status_msg": "insufficient quota",
            }
        }

    def download(self, *args, **kwargs):
        raise AssertionError("download should not run")


class ForbiddenImageTransport:
    def __init__(self) -> None:
        self.calls = 0

    def request_json(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("existing first frame must be reused")

    def download(self, *args, **kwargs):
        raise AssertionError("image transport download should not run")


def test_live_probe_reuses_existing_first_frame_without_image_request(
    tmp_path: Path, monkeypatch
) -> None:
    first_frame = tmp_path / "first_frame.jpg"
    first_frame.write_bytes(b"\xff\xd8\xff\xe0image")
    monkeypatch.setattr(probe, "FIRST_FRAME_FILE", first_frame)
    monkeypatch.setattr(probe, "VIDEO_FILE", tmp_path / "video.mp4")
    monkeypatch.setattr(probe, "OUTPUT_DIR", tmp_path)
    image_inner = ForbiddenImageTransport()
    video_inner = RejectingVideoTransport()
    image_transport = probe.CountingTransport(image_inner)
    video_transport = probe.CountingTransport(video_inner)

    with pytest.raises(MiniMaxAccountError, match="2056"):
        probe.run_live(
            load_package(),
            video_transport,
            image_transport=image_transport,
            shot_id="shot_001",
            poll_interval=10,
            overall_timeout=60,
        )

    assert image_inner.calls == 0
    assert video_inner.calls == ["/v1/video_generation"]


def test_task_id_is_persisted_for_safe_resume(tmp_path: Path) -> None:
    state_file = tmp_path / "task.json"

    probe.save_task_state("task-123", state_file=state_file)

    assert '"task_id": "task-123"' in state_file.read_text(encoding="utf-8")


class TraceTransport:
    def request_json(self, *args, **kwargs):
        return {
            "task_id": "task-456",
            "base_resp": {"status_code": 0, "status_msg": "success"},
            "authorization": "must-not-be-written",
        }

    def download(self, *args, **kwargs):
        raise AssertionError("download is not expected")


def test_counting_transport_persists_redacted_response_before_return(
    tmp_path: Path,
) -> None:
    trace_file = tmp_path / "trace.json"
    transport = probe.CountingTransport(TraceTransport(), trace_file=trace_file)

    response = transport.request_json(
        "POST",
        "/v1/video_generation",
        payload={"prompt": "test"},
        params=None,
        timeout=10,
    )

    persisted = trace_file.read_text(encoding="utf-8")
    assert response["task_id"] == "task-456"
    assert '"task_id": "task-456"' in persisted
    assert "must-not-be-written" not in persisted
    assert "[REDACTED]" in persisted


def test_trace_removes_temporary_download_url_credentials() -> None:
    value = probe.redact_sensitive(
        {
            "download_url": (
                "https://cdn.example.com/video.mp4?"
                "OSSAccessKeyId=temp&Signature=secret#fragment"
            )
        }
    )

    assert value["download_url"] == "https://cdn.example.com/video.mp4"


class SuccessfulResumeTransport:
    def __init__(self, output_file: Path) -> None:
        self.output_file = output_file
        self.calls: list[str] = []
        self.responses = [
            {
                "task_id": "task-resume",
                "status": "Processing",
                "video_width": 0,
                "video_height": 0,
                "base_resp": {"status_code": 0, "status_msg": "success"},
            },
            {
                "task_id": "task-resume",
                "status": "Success",
                "file_id": 987,
                "video_width": 768,
                "video_height": 1366,
                "base_resp": {"status_code": 0, "status_msg": "success"},
            },
            {
                "task_id": "task-resume",
                "status": "Success",
                "file_id": 987,
                "video_width": 768,
                "video_height": 1366,
                "base_resp": {"status_code": 0, "status_msg": "success"},
            },
            {
                "file": {
                    "file_id": 987,
                    "bytes": 20,
                    "download_url": "https://filecdn.minimax.chat/video.mp4",
                },
                "base_resp": {"status_code": 0, "status_msg": "success"},
            },
        ]

    def request_json(self, method, path, **kwargs):
        self.calls.append(path)
        return self.responses.pop(0)

    def download(self, url, output_file, **kwargs):
        Path(output_file).write_bytes(b"\x00\x00\x00\x18ftypmp42mock-video")
        return Path(output_file)


def test_resume_existing_task_never_submits_a_new_video(
    tmp_path: Path, monkeypatch
) -> None:
    video_file = tmp_path / "video.mp4"
    monkeypatch.setattr(probe, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(probe, "VIDEO_FILE", video_file)
    monkeypatch.setattr(probe.time, "sleep", lambda _: None)
    inner = SuccessfulResumeTransport(video_file)
    transport = probe.CountingTransport(inner)

    summary = probe.run_live(
        load_package(),
        transport,
        resume_task_id="task-resume",
        shot_id="shot_001",
        poll_interval=10,
        overall_timeout=60,
    )

    assert summary["passed"] is True
    assert summary["task_id"] == "task-resume"
    assert "/v1/video_generation" not in inner.calls
    assert video_file.exists()
