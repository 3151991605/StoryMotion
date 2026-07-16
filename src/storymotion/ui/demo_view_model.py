from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from storymotion.models import StoryMotionBundle


@dataclass(frozen=True)
class StageView:
    key: str
    index: str
    label: str
    status: str
    detail: str


@dataclass(frozen=True)
class DemoViewModel:
    bundle: StoryMotionBundle
    summary: dict[str, Any]
    stages: tuple[StageView, ...]
    shot_rows: tuple[dict[str, str | float], ...]
    duration_seconds: float
    local_video_passed: bool
    hailuo_status_code: int | None
    video_file: Path


def _require_file(path: Path) -> Path:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"required demo artifact was not found: {path}")
    return path


def _resolve_artifact(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path(root) / path


def load_demo_view_model(
    *,
    root: Path,
    bundle_file: Path,
    summary_file: Path,
) -> DemoViewModel:
    root = Path(root)
    bundle_path = _require_file(bundle_file)
    summary_path = _require_file(summary_file)
    bundle = StoryMotionBundle.model_validate_json(
        bundle_path.read_text(encoding="utf-8")
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    video_file = _require_file(_resolve_artifact(root, summary["video_file"]))
    hailuo = summary.get("real_video_provider", {})

    stages = (
        StageView("story", "01", "故事创作", "passed", "StoryPackage 协议通过"),
        StageView(
            "screenplay", "02", "漫剧改编", "passed", "ScreenplayPackage 协议通过"
        ),
        StageView(
            "storyboard",
            "03",
            "镜头设计",
            "passed",
            f"{len(bundle.storyboard.shots)} 个镜头 · 时长闭合",
        ),
        StageView(
            "media",
            "04",
            "媒体成片",
            "warning" if hailuo.get("status") else "passed",
            "Mock MP4 已通过 · 海螺额度待补充",
        ),
    )
    shot_rows = tuple(
        {
            "shot_id": shot.shot_id,
            "scene_id": shot.scene_id,
            "duration": shot.duration,
            "shot_type": shot.shot_type,
            "camera_movement": shot.camera_movement,
            "visual_description": shot.visual_description,
            "video_prompt": shot.video_prompt,
        }
        for shot in bundle.storyboard.shots
    )
    return DemoViewModel(
        bundle=bundle,
        summary=summary,
        stages=stages,
        shot_rows=shot_rows,
        duration_seconds=float(summary["video_duration_seconds"]),
        local_video_passed=bool(summary["passed"]),
        hailuo_status_code=hailuo.get("last_api_status_code"),
        video_file=video_file,
    )
