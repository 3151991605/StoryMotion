"""Resumable, single-job Hailuo rendering with continuity-frame chaining."""

from __future__ import annotations

import base64
import json
import subprocess
import time
from pathlib import Path
from typing import Mapping, Protocol

import imageio_ffmpeg

from storymotion.models import ImageGenerationRequest, MediaTaskStatus, Shot, ShotPackage, VideoGenerationRequest
from storymotion.providers import MiniMaxImageProvider
from storymotion.providers.minimax_media import MiniMaxMediaError
from .prompt_director import render_video_prompt_for_shot


class VideoProvider(Protocol):
    def submit(self, request: VideoGenerationRequest): ...
    def get_status(self, task_id: str): ...
    def get_result(self, task_id: str): ...
    def download(self, result, output_file: Path) -> Path: ...


class HailuoJobInProgress(RuntimeError):
    """A persisted job must be resumed before submitting another one."""


def hailuo_duration(shot: Shot) -> int:
    return 10 if shot.duration > 6 else 6


class HailuoVideoRenderer:
    def __init__(
        self,
        provider: VideoProvider,
        *,
        image_provider: MiniMaxImageProvider | None = None,
        character_references: Mapping[str, Path] | None = None,
        poll_interval_seconds: float = 10.0,
        overall_timeout_seconds: float = 900.0,
    ) -> None:
        self.provider = provider
        self.image_provider = image_provider
        self.character_references = {
            character_id: Path(path)
            for character_id, path in (character_references or {}).items()
        }
        self.poll_interval_seconds = poll_interval_seconds
        self.overall_timeout_seconds = overall_timeout_seconds

    def render(self, package: ShotPackage, *, output_dir: Path) -> Path:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        state_file = output_dir / "render_state.json"
        active_file = output_dir.parent / "active_hailuo_job.json"
        self._claim_job(active_file, output_dir)
        state = self._load_state(state_file, package)
        self._save_state(state_file, state)
        deadline = time.monotonic() + self.overall_timeout_seconds
        clips: list[Path] = []
        previous_last_frame: Path | None = None
        previous_scene_id: str | None = None
        for shot in package.shots:
            first_frame = previous_last_frame if shot.scene_id == previous_scene_id else None
            clip = self._render_shot(
                shot, output_dir, deadline, first_frame, state, state_file
            )
            clips.append(clip)
            previous_last_frame = self._extract_last_frame(
                clip, output_dir / f"{shot.shot_id}_last.jpg"
            )
            previous_scene_id = shot.scene_id
        output = self._concatenate(clips, package.target_duration, output_dir)
        state["status"] = "completed"
        self._save_state(state_file, state)
        active_file.unlink(missing_ok=True)
        return output

    def _render_shot(
        self,
        shot: Shot,
        output_dir: Path,
        deadline: float,
        first_frame: Path | None,
        state: dict,
        state_file: Path,
    ) -> Path:
        clip_file = output_dir / f"{shot.shot_id}.mp4"
        shot_state = state["shots"].setdefault(shot.shot_id, {})
        if clip_file.is_file():
            return clip_file
        if first_frame is None and self.image_provider is not None:
            first_file = output_dir / f"{shot.shot_id}_first.jpg"
            if first_file.is_file():
                first_frame = first_file
            else:
                reference_image = self._character_reference_for(shot)
                image = self.image_provider.generate(
                    ImageGenerationRequest(
                        prompt=shot.image_prompt,
                        aspect_ratio="9:16",
                        reference_image=(
                            self._data_url(reference_image)
                            if reference_image is not None
                            else None
                        ),
                    ),
                    output_file=first_file,
                )
                first_frame = image.path
        task_id = shot_state.get("task_id")
        if task_id:
            task = self.provider.get_status(task_id)
        else:
            task = self.provider.submit(
                VideoGenerationRequest(
                    prompt=render_video_prompt_for_shot(shot),
                    duration=hailuo_duration(shot),
                    resolution="768P",
                    first_frame_image=self._data_url(first_frame) if first_frame else None,
                )
            )
            shot_state.update(task_id=task.task_id, status="submitted")
            self._save_state(state_file, state)
        while task.status in (MediaTaskStatus.PENDING, MediaTaskStatus.RUNNING):
            if time.monotonic() >= deadline:
                raise MiniMaxMediaError("Hailuo video generation exceeded overall timeout")
            time.sleep(self.poll_interval_seconds)
            task = self.provider.get_status(task.task_id)
            shot_state["status"] = task.status.value
            self._save_state(state_file, state)
        if task.status is not MediaTaskStatus.SUCCEEDED:
            shot_state["status"] = "failed"
            self._save_state(state_file, state)
            raise MiniMaxMediaError(f"Hailuo task {task.task_id} failed: {task.error}")
        result = self.provider.get_result(task.task_id)
        clip = self.provider.download(result, clip_file)
        shot_state["status"] = "downloaded"
        self._save_state(state_file, state)
        return clip

    def _character_reference_for(self, shot: Shot) -> Path | None:
        for character_id in shot.character_ids:
            reference = self.character_references.get(character_id)
            if reference is not None and reference.is_file():
                return reference
        return None

    @staticmethod
    def _load_state(state_file: Path, package: ShotPackage) -> dict:
        if state_file.is_file():
            return json.loads(state_file.read_text(encoding="utf-8"))
        return {"status": "running", "target_duration": package.target_duration, "shots": {}}

    @staticmethod
    def _save_state(state_file: Path, state: dict) -> None:
        temporary = state_file.with_suffix(".part")
        temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(state_file)

    @staticmethod
    def _claim_job(active_file: Path, output_dir: Path) -> None:
        if active_file.is_file():
            active = json.loads(active_file.read_text(encoding="utf-8"))
            if Path(active.get("output_dir", "")).resolve() != output_dir.resolve():
                raise HailuoJobInProgress("已有视频任务在运行；请继续原任务，避免重复扣费。")
            return
        active_file.write_text(
            json.dumps({"output_dir": str(output_dir.resolve())}, ensure_ascii=False),
            encoding="utf-8",
        )

    @staticmethod
    def _data_url(path: Path) -> str:
        raw = Path(path).read_bytes()
        media_type = "image/png" if raw.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg"
        return f"data:{media_type};base64,{base64.b64encode(raw).decode('ascii')}"

    @staticmethod
    def _extract_last_frame(clip: Path, output: Path) -> Path:
        completed = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-sseof", "-0.1", "-i", str(clip), "-frames:v", "1", str(output)],
            capture_output=True, text=True, check=False,
        )
        if completed.returncode != 0 or not output.is_file():
            raise RuntimeError("FFmpeg could not extract a continuity frame: " + completed.stderr[-500:])
        return output

    @staticmethod
    def _concatenate(clips: list[Path], duration: int, output_dir: Path) -> Path:
        manifest = output_dir / "clips.txt"
        manifest.write_text("".join(f"file '{clip.resolve().as_posix()}'\n" for clip in clips), encoding="utf-8")
        output = output_dir / "storymotion_hailuo.mp4"
        completed = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-f", "concat", "-safe", "0", "-i", str(manifest), "-t", str(duration), "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", str(output)],
            capture_output=True, text=True, check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError("FFmpeg video concatenation failed: " + completed.stderr[-1000:])
        return output
