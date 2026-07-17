from storymotion.models import Shot
import pytest

from storymotion.services.hailuo_video_renderer import HailuoJobInProgress, HailuoVideoRenderer, hailuo_duration


def make_shot(duration: float) -> Shot:
    return Shot(
        shot_id="shot_001", scene_id="scene_001", duration=duration,
        shot_type="medium", camera_movement="static", visual_description="测试镜头",
        image_prompt="test image", video_prompt="test video",
    )


def test_maps_storyboard_shots_to_hailuo_supported_durations() -> None:
    assert hailuo_duration(make_shot(6)) == 6
    assert hailuo_duration(make_shot(6.1)) == 10
    assert hailuo_duration(make_shot(10)) == 10


def test_refuses_a_second_active_job(tmp_path) -> None:
    active = tmp_path / "active_hailuo_job.json"
    HailuoVideoRenderer._claim_job(active, tmp_path / "first")
    with pytest.raises(HailuoJobInProgress):
        HailuoVideoRenderer._claim_job(active, tmp_path / "second")
