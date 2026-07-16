"""Run the deterministic StoryMotion feasibility chain from JSON to Mock MP4."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

from storymotion.models import ProjectBrief, ScreenplayPackage, StoryPackage
from storymotion.providers import MockVideoProvider, RuleShotProvider
from storymotion.services import DemoPipeline


ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_DIR = ROOT / "outputs" / "verification"
DEFAULT_BRIEF_FILE = VERIFICATION_DIR / "minimax_m3_project_brief_run_01.json"
DEFAULT_STORY_FILE = VERIFICATION_DIR / "story_graph" / "story_package.json"
DEFAULT_SCREENPLAY_FILE = (
    VERIFICATION_DIR / "screenplay" / "screenplay_package_repaired.json"
)
DEFAULT_OUTPUT_DIR = VERIFICATION_DIR / "end_to_end_demo"
DEFAULT_SUMMARY_FILE = VERIFICATION_DIR / "end_to_end_demo_summary.json"


def load_inputs(
    *,
    brief_file: Path,
    story_file: Path,
    screenplay_file: Path,
) -> tuple[ProjectBrief, StoryPackage, ScreenplayPackage]:
    brief = ProjectBrief.model_validate_json(
        Path(brief_file).read_text(encoding="utf-8")
    )
    story = StoryPackage.model_validate_json(
        Path(story_file).read_text(encoding="utf-8")
    )
    screenplay = ScreenplayPackage.model_validate_json(
        Path(screenplay_file).read_text(encoding="utf-8")
    )
    return brief, story, screenplay


def find_workspace_tool(root: Path, name: str) -> Path:
    matches = sorted(
        (Path(root) / ".tools" / "ffmpeg" / "runtime").glob(
            f"**/{name}.exe"
        )
    )
    if not matches:
        raise FileNotFoundError(f"workspace-local {name}.exe was not found")
    return matches[0]


def probe_video(ffprobe: Path, video_file: Path) -> dict:
    completed = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate",
            "-of",
            "json",
            str(video_file),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return json.loads(completed.stdout)


def relative_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path.resolve())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", type=Path, default=DEFAULT_BRIEF_FILE)
    parser.add_argument("--story", type=Path, default=DEFAULT_STORY_FILE)
    parser.add_argument("--screenplay", type=Path, default=DEFAULT_SCREENPLAY_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_FILE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    brief, story, screenplay = load_inputs(
        brief_file=args.brief,
        story_file=args.story,
        screenplay_file=args.screenplay,
    )
    ffmpeg = find_workspace_tool(ROOT, "ffmpeg")
    ffprobe = find_workspace_tool(ROOT, "ffprobe")
    pipeline = DemoPipeline(
        shot_provider=RuleShotProvider(),
        video_provider=MockVideoProvider(ffmpeg_path=ffmpeg),
    )

    started = time.perf_counter()
    result = pipeline.run(
        brief=brief,
        story=story,
        screenplay=screenplay,
        output_dir=args.output_dir,
    )
    elapsed = round(time.perf_counter() - started, 3)
    probe = probe_video(ffprobe, result.video_path)
    video_stream = next(
        stream for stream in probe["streams"] if stream["codec_type"] == "video"
    )
    audio_stream = next(
        stream for stream in probe["streams"] if stream["codec_type"] == "audio"
    )
    duration = float(probe["format"]["duration"])
    passed = (
        abs(duration - result.bundle.storyboard.target_duration) <= 0.1
        and video_stream["width"] == 720
        and video_stream["height"] == 1280
        and video_stream["codec_name"] == "h264"
        and audio_stream["codec_name"] == "aac"
    )
    summary = {
        "passed": passed,
        "pipeline": "existing MiniMax artifacts -> RuleShotProvider -> MockVideoProvider",
        "network_requests": 0,
        "model_tokens": 0,
        "real_video_provider": {
            "provider": "MiniMax Hailuo",
            "status": "blocked_by_account_quota",
            "last_api_status_code": 2056,
        },
        "target_duration_seconds": result.bundle.storyboard.target_duration,
        "video_duration_seconds": duration,
        "shot_count": len(result.bundle.storyboard.shots),
        "elapsed_seconds": elapsed,
        "width": video_stream["width"],
        "height": video_stream["height"],
        "video_codec": video_stream["codec_name"],
        "audio_codec": audio_stream["codec_name"],
        "bundle_file": relative_path(result.bundle_path),
        "storyboard_file": relative_path(result.storyboard_path),
        "video_file": relative_path(result.video_path),
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved: {args.summary}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
