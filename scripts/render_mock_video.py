"""Render and verify a 60-second vertical Mock MP4 from RuleShotProvider output."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from storymotion.models import ShotPackage
from storymotion.providers import MockVideoProvider


ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_DIR = ROOT / "outputs" / "verification"
SHOT_FILE = VERIFICATION_DIR / "rule_shots" / "shot_package.json"
OUTPUT_DIR = VERIFICATION_DIR / "mock_video"
VIDEO_FILE = OUTPUT_DIR / "storymotion_mock.mp4"
PROBE_FILE = OUTPUT_DIR / "ffprobe.json"
SUMMARY_FILE = VERIFICATION_DIR / "mock_video_summary.json"


def find_tool(name: str) -> Path:
    matches = sorted(
        (ROOT / ".tools" / "ffmpeg" / "runtime").glob(f"**/{name}.exe")
    )
    if not matches:
        raise FileNotFoundError(f"workspace-local {name}.exe was not found")
    return matches[0]


def main() -> int:
    package = ShotPackage.model_validate_json(SHOT_FILE.read_text(encoding="utf-8"))
    ffmpeg = find_tool("ffmpeg")
    ffprobe = find_tool("ffprobe")
    provider = MockVideoProvider(ffmpeg_path=ffmpeg)

    started = time.perf_counter()
    rendered = provider.render(package, output_file=VIDEO_FILE)
    render_seconds = round(time.perf_counter() - started, 3)

    probe = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate",
            "-of",
            "json",
            str(rendered),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    probe_data = json.loads(probe.stdout)
    PROBE_FILE.write_text(
        json.dumps(probe_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    video_stream = next(
        stream for stream in probe_data["streams"] if stream["codec_type"] == "video"
    )
    audio_stream = next(
        stream for stream in probe_data["streams"] if stream["codec_type"] == "audio"
    )
    duration = float(probe_data["format"]["duration"])
    passed = (
        abs(duration - package.target_duration) <= 0.1
        and video_stream["width"] == 720
        and video_stream["height"] == 1280
        and video_stream["codec_name"] == "h264"
        and audio_stream["codec_name"] == "aac"
    )
    summary = {
        "provider": "MockVideoProvider",
        "passed": passed,
        "network_requests": 0,
        "model_tokens": 0,
        "source_shot_package": str(SHOT_FILE.relative_to(ROOT)),
        "shot_count": len(package.shots),
        "timeline_entries": len(package.shots),
        "render_seconds": render_seconds,
        "video_duration_seconds": duration,
        "width": video_stream["width"],
        "height": video_stream["height"],
        "frame_rate": video_stream["r_frame_rate"],
        "video_codec": video_stream["codec_name"],
        "audio_codec": audio_stream["codec_name"],
        "file_size_bytes": int(probe_data["format"]["size"]),
        "video_file": str(VIDEO_FILE.relative_to(ROOT)),
        "timeline_file": str((OUTPUT_DIR / "timeline.ass").relative_to(ROOT)),
        "ffprobe_file": str(PROBE_FILE.relative_to(ROOT)),
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved: {SUMMARY_FILE}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
