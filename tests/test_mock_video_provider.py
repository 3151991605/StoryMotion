from __future__ import annotations

from pathlib import Path

from storymotion.models import ScreenplayPackage
from storymotion.providers import MockVideoProvider, RuleShotProvider


SCREENPLAY_FILE = (
    Path(__file__).resolve().parents[1]
    / "outputs"
    / "verification"
    / "screenplay"
    / "screenplay_package_repaired.json"
)


def load_shot_package():
    screenplay = ScreenplayPackage.model_validate_json(
        SCREENPLAY_FILE.read_text(encoding="utf-8")
    )
    return RuleShotProvider().generate(screenplay)


def test_ass_timeline_has_one_event_per_shot_and_exact_end() -> None:
    package = load_shot_package()
    provider = MockVideoProvider(ffmpeg_path=Path("ffmpeg.exe"))

    ass = provider.build_ass_timeline(package)

    assert ass.count("Dialogue: 0,") == 6
    assert "0:00:00.00,0:00:10.00" in ass
    assert "0:00:50.00,0:01:00.00" in ass
    assert "幽冥回溯·刹那之塔" in ass
    assert "scene_003" in ass


def test_ffmpeg_command_is_vertical_h264_and_overwrite_safe(tmp_path: Path) -> None:
    package = load_shot_package()
    provider = MockVideoProvider(ffmpeg_path=Path("ffmpeg.exe"))
    command = provider.build_ffmpeg_command(
        package,
        ass_file=tmp_path / "timeline.ass",
        output_file=tmp_path / "mock.mp4",
    )
    joined = " ".join(str(part) for part in command)

    assert command[1:3] == ["-y", "-hide_banner"]
    assert joined.count("color=c=") == 6
    assert "s=720x1280" in joined
    assert "libx264" in command
    assert "aac" in command
    assert "subtitles=timeline.ass:charenc=UTF-8" in joined
    assert command[-1].endswith("mock.mp4")
