"""Prepare or explicitly run one image-to-video Hailuo feasibility probe."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit, urlunsplit

from pydantic import ValidationError

from storymotion.models import (
    ImageGenerationRequest,
    MediaTaskStatus,
    Shot,
    ShotPackage,
    VideoGenerationRequest,
    VideoTask,
)
from storymotion.providers import (
    HailuoVideoProvider,
    MiniMaxImageProvider,
    MiniMaxMediaError,
    UrllibMiniMaxMediaTransport,
)
from storymotion.providers.minimax_media import MiniMaxMediaTransport
from verify_minimax_access import ENV_FILE, load_local_env


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_FILE = ROOT / "outputs/verification/minimax_shot_provider_package.json"
OUTPUT_DIR = ROOT / "outputs/verification/hailuo_single_shot"
SUMMARY_FILE = ROOT / "outputs/verification/hailuo_single_shot_summary.json"
FIRST_FRAME_FILE = OUTPUT_DIR / "shot_001_first_frame.jpg"
VIDEO_FILE = OUTPUT_DIR / "shot_001.mp4"
TASK_STATE_FILE = OUTPUT_DIR / "shot_001_task.json"
TRACE_FILE = OUTPUT_DIR / "shot_001_trace.json"


def display_path(path: Path) -> str:
    path = Path(path)
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in ("authorization", "api_key", "secret", "token")):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str) and value.startswith(("https://", "http://")):
        parsed = urlsplit(value)
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    if isinstance(value, str) and len(value) > 4000:
        return value[:4000] + "...[TRUNCATED]"
    return value


class CountingTransport:
    def __init__(
        self,
        inner: MiniMaxMediaTransport,
        *,
        trace_file: Path | None = None,
    ) -> None:
        self.inner = inner
        self.requests: list[tuple[str, str]] = []
        self.downloads = 0
        self.trace_file = Path(trace_file) if trace_file is not None else None
        self.events: list[dict[str, Any]] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None,
        params: dict[str, str] | None,
        timeout: float,
    ) -> dict[str, Any]:
        self.requests.append((method, path))
        try:
            response = self.inner.request_json(
                method,
                path,
                payload=payload,
                params=params,
                timeout=timeout,
            )
        except Exception as exc:
            self._record(
                {
                    "method": method,
                    "path": path,
                    "error_type": type(exc).__name__,
                }
            )
            raise
        self._record(
            {
                "method": method,
                "path": path,
                "response": redact_sensitive(response),
            }
        )
        return response

    def download(
        self,
        url: str,
        output_file: Path,
        *,
        timeout: float,
        max_bytes: int,
    ) -> Path:
        self.downloads += 1
        return self.inner.download(
            url, output_file, timeout=timeout, max_bytes=max_bytes
        )

    def _record(self, event: dict[str, Any]) -> None:
        self.events.append(event)
        if self.trace_file is None:
            return
        self.trace_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.trace_file.with_suffix(self.trace_file.suffix + ".part")
        temporary.write_text(
            json.dumps(self.events, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.trace_file)


def select_shot(package: ShotPackage, shot_id: str) -> Shot:
    for shot in package.shots:
        if shot.shot_id == shot_id:
            return shot
    raise ValueError(f"unknown shot ID: {shot_id}")


def build_requests(shot: Shot) -> tuple[ImageGenerationRequest, VideoGenerationRequest]:
    image_request = ImageGenerationRequest(
        prompt=shot.image_prompt,
        aspect_ratio="9:16",
    )
    video_request = VideoGenerationRequest(
        prompt=shot.video_prompt,
        duration=6,
        resolution="768P",
    )
    return image_request, video_request


def build_dry_run_summary(
    package: ShotPackage, *, shot_id: str = "shot_001"
) -> dict[str, Any]:
    shot = select_shot(package, shot_id)
    image_request, video_request = build_requests(shot)
    return {
        "mode": "dry-run",
        "passed": True,
        "network_requests": 0,
        "automatic_retries": 0,
        "shot_id": shot.shot_id,
        "source_shot_duration": shot.duration,
        "image_request": {
            "model": "image-01",
            "aspect_ratio": image_request.aspect_ratio,
            "prompt_characters": len(image_request.prompt),
            "output": str(FIRST_FRAME_FILE.relative_to(ROOT)),
        },
        "video_request": {
            "model": "MiniMax-Hailuo-2.3",
            "duration": video_request.duration,
            "resolution": video_request.resolution,
            "prompt_characters": len(video_request.prompt),
            "first_frame_source": "generated-image",
            "output": str(VIDEO_FILE.relative_to(ROOT)),
        },
    }


def image_to_data_url(path: Path, *, max_bytes: int = 20_000_000) -> str:
    raw = Path(path).read_bytes()
    if not raw or len(raw) > max_bytes:
        raise ValueError("first-frame image is empty or exceeds configured limit")
    if raw.startswith(b"\xff\xd8\xff"):
        media_type = "image/jpeg"
    elif raw.startswith(b"\x89PNG\r\n\x1a\n"):
        media_type = "image/png"
    elif len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        media_type = "image/webp"
    else:
        raise ValueError("first-frame file is not a supported image")
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def get_video_api_key(environment: Mapping[str, str]) -> str:
    api_key = environment.get("MINIMAX_VIDEO_API_KEY", "").strip()
    if not api_key:
        raise ValueError("MINIMAX_VIDEO_API_KEY is not configured")
    return api_key


def save_task_state(
    task_id: str,
    *,
    state_file: Path = TASK_STATE_FILE,
    shot_id: str = "shot_001",
) -> None:
    state_file = Path(state_file)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps(
            {
                "task_id": task_id,
                "shot_id": shot_id,
                "model": "MiniMax-Hailuo-2.3",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def run_live(
    package: ShotPackage,
    video_transport: CountingTransport,
    *,
    image_transport: CountingTransport | None = None,
    resume_task_id: str | None = None,
    shot_id: str,
    poll_interval: float,
    overall_timeout: float,
) -> dict[str, Any]:
    shot = select_shot(package, shot_id)
    image_request, base_video_request = build_requests(shot)
    video_provider = HailuoVideoProvider(video_transport)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    first_frame_reused = FIRST_FRAME_FILE.exists()
    if resume_task_id is not None:
        task = VideoTask(
            provider="minimax-hailuo",
            task_id=resume_task_id,
            status=MediaTaskStatus.PENDING,
        )
    else:
        if first_frame_reused:
            first_frame_data_url = image_to_data_url(FIRST_FRAME_FILE)
        else:
            if image_transport is None:
                raise MiniMaxMediaError(
                    "first frame is missing and no image transport is configured"
                )
            image_provider = MiniMaxImageProvider(image_transport)
            image = image_provider.generate(
                image_request, output_file=FIRST_FRAME_FILE
            )
            first_frame_data_url = image_to_data_url(image.path)
        video_request = VideoGenerationRequest(
            prompt=base_video_request.prompt,
            duration=base_video_request.duration,
            resolution=base_video_request.resolution,
            first_frame_image=first_frame_data_url,
        )
        task = video_provider.submit(video_request)
        save_task_state(task.task_id, shot_id=shot.shot_id)
    polls = 0
    while task.status in (MediaTaskStatus.PENDING, MediaTaskStatus.RUNNING):
        if time.monotonic() - started >= overall_timeout:
            raise MiniMaxMediaError("Hailuo task exceeded overall timeout")
        time.sleep(poll_interval)
        task = video_provider.get_status(task.task_id)
        polls += 1
    if task.status is MediaTaskStatus.FAILED:
        raise MiniMaxMediaError(f"Hailuo task failed: {task.error}")
    result = video_provider.get_result(task.task_id)
    video_provider.download(result, VIDEO_FILE)
    return {
        "mode": "live",
        "passed": True,
        "automatic_retries": 0,
        "shot_id": shot.shot_id,
        "task_id": task.task_id,
        "resumed": resume_task_id is not None,
        "file_id": result.file_id,
        "polls": polls,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "first_frame_file": display_path(FIRST_FRAME_FILE),
        "first_frame_reused": first_frame_reused,
        "video_file": display_path(VIDEO_FILE),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=PACKAGE_FILE)
    parser.add_argument("--shot-id", default="shot_001")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--submit", action="store_true")
    action.add_argument("--resume-task-id")
    parser.add_argument("--poll-interval", type=float, default=10.0)
    parser.add_argument("--overall-timeout", type=float, default=600.0)
    args = parser.parse_args(argv)
    if args.poll_interval < 5 or args.overall_timeout < 60:
        parser.error("poll interval must be >=5s and overall timeout >=60s")
    try:
        package = ShotPackage.model_validate_json(
            args.package.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as exc:
        print(f"Invalid ShotPackage: {exc}", file=sys.stderr)
        return 2

    if not args.submit and not args.resume_task_id:
        try:
            summary = build_dry_run_summary(package, shot_id=args.shot_id)
        except (ValueError, ValidationError) as exc:
            print(f"Invalid dry-run input: {exc}", file=sys.stderr)
            return 2
    else:
        load_local_env(ENV_FILE)
        try:
            video_api_key = get_video_api_key(os.environ)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        base_url = os.getenv("MINIMAX_API_BASE", "https://api.minimaxi.com")
        video_counted = CountingTransport(
            UrllibMiniMaxMediaTransport(
                api_key=video_api_key, base_url=base_url
            ),
            trace_file=TRACE_FILE,
        )
        image_counted: CountingTransport | None = None
        image_api_key = os.getenv("MINIMAX_API_KEY", "").strip()
        if args.submit and not FIRST_FRAME_FILE.exists():
            if not image_api_key:
                print(
                    "First frame is missing and MINIMAX_API_KEY is not configured",
                    file=sys.stderr,
                )
                return 2
            image_counted = CountingTransport(
                UrllibMiniMaxMediaTransport(
                    api_key=image_api_key, base_url=base_url
                )
            )
        try:
            summary = run_live(
                package,
                video_counted,
                image_transport=image_counted,
                resume_task_id=args.resume_task_id,
                shot_id=args.shot_id,
                poll_interval=args.poll_interval,
                overall_timeout=args.overall_timeout,
            )
        except (MiniMaxMediaError, OSError, ValueError, ValidationError) as exc:
            summary = {
                "mode": "live",
                "passed": False,
                "automatic_retries": 0,
                "shot_id": args.shot_id,
                "error": (
                    str(exc)
                    .replace(video_api_key, "[REDACTED]")
                    .replace(image_api_key, "[REDACTED]")
                ),
                "first_frame_generated": FIRST_FRAME_FILE.exists(),
                "first_frame_file": (
                    str(FIRST_FRAME_FILE.relative_to(ROOT))
                    if FIRST_FRAME_FILE.exists()
                    else None
                ),
                "video_generated": VIDEO_FILE.exists(),
                "resume_task_id": args.resume_task_id,
            }
        image_requests = image_counted.requests if image_counted else []
        image_downloads = image_counted.downloads if image_counted else 0
        summary["network_requests"] = (
            len(image_requests)
            + image_downloads
            + len(video_counted.requests)
            + video_counted.downloads
        )
        summary["request_paths"] = [
            path for _, path in image_requests + video_counted.requests
        ]

    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_FILE.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved: {SUMMARY_FILE}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
