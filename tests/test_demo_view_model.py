from __future__ import annotations

from pathlib import Path

import pytest

from storymotion.ui import load_demo_view_model


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_FILE = (
    ROOT
    / "outputs"
    / "verification"
    / "end_to_end_demo"
    / "storymotion_bundle.json"
)
SUMMARY_FILE = ROOT / "outputs" / "verification" / "end_to_end_demo_summary.json"


def test_loads_dashboard_view_model_from_verified_artifacts() -> None:
    view = load_demo_view_model(
        root=ROOT,
        bundle_file=BUNDLE_FILE,
        summary_file=SUMMARY_FILE,
    )

    assert [stage.key for stage in view.stages] == [
        "story",
        "screenplay",
        "storyboard",
        "media",
    ]
    assert [stage.status for stage in view.stages] == [
        "passed",
        "passed",
        "passed",
        "warning",
    ]
    assert view.duration_seconds == 60
    assert len(view.shot_rows) == 6
    assert view.local_video_passed is True
    assert view.hailuo_status_code == 2056
    assert view.video_file.is_file()


def test_missing_artifact_names_the_missing_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing-bundle.json"

    with pytest.raises(FileNotFoundError, match="missing-bundle.json"):
        load_demo_view_model(
            root=ROOT,
            bundle_file=missing,
            summary_file=SUMMARY_FILE,
        )
