from __future__ import annotations

from pathlib import Path

from storymotion.models import StoryMotionBundle
from storymotion.providers import RuleShotProvider
from storymotion.services import DemoPipeline


FIXTURE_FILE = (
    Path(__file__).resolve().parent / "fixtures" / "valid_storymotion_bundle.json"
)


class RecordingVideoProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[object, Path]] = []

    def render(self, package, *, output_file: Path) -> Path:
        self.calls.append((package, output_file))
        output_file.write_bytes(b"mock mp4")
        return output_file


def test_runs_validated_bundle_and_video_pipeline(tmp_path: Path) -> None:
    fixture = StoryMotionBundle.model_validate_json(
        FIXTURE_FILE.read_text(encoding="utf-8")
    )
    video_provider = RecordingVideoProvider()
    pipeline = DemoPipeline(
        shot_provider=RuleShotProvider(),
        video_provider=video_provider,
    )

    result = pipeline.run(
        brief=fixture.brief,
        story=fixture.story,
        screenplay=fixture.screenplay,
        output_dir=tmp_path,
    )

    assert result.bundle.storyboard.total_shot_duration == 60
    assert result.bundle_path == tmp_path / "storymotion_bundle.json"
    assert result.storyboard_path == tmp_path / "shot_package.json"
    assert result.video_path == tmp_path / "storymotion_mock.mp4"
    assert StoryMotionBundle.model_validate_json(
        result.bundle_path.read_text(encoding="utf-8")
    ) == result.bundle
    assert result.storyboard_path.is_file()
    assert result.video_path.read_bytes() == b"mock mp4"
    assert video_provider.calls == [(result.bundle.storyboard, result.video_path)]
