from pathlib import Path

from storymotion.models import (
    GeneratedImage,
    KeyframeContract,
    MediaTaskStatus,
    Shot,
    VideoTask,
)
import pytest

from storymotion.services.hailuo_video_renderer import HailuoJobInProgress, HailuoVideoRenderer, hailuo_duration
from storymotion.providers.minimax_media import MiniMaxMediaError


def make_shot(duration: float) -> Shot:
    return Shot(
        shot_id="shot_001", scene_id="scene_001", duration=duration,
        shot_type="medium", camera_movement="static", visual_description="测试镜头",
        character_ids=["char_001"],
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


def test_prefers_planned_shot_keyframe_over_previous_clip_frame(tmp_path) -> None:
    shot = make_shot(6)
    planned = tmp_path / "planned.png"
    previous = tmp_path / "previous.jpg"
    planned.write_bytes(b"planned")

    assert HailuoVideoRenderer._first_frame_for_shot(
        shot, {shot.shot_id: planned}, previous
    ) == planned


class RecordingFailedProvider:
    def __init__(self) -> None:
        self.requests = []

    def submit(self, request):
        self.requests.append(request)
        return VideoTask(
            provider="test",
            task_id="task_001",
            status=MediaTaskStatus.FAILED,
            error="intentional test failure",
        )


class RecordingImageProvider:
    def __init__(self) -> None:
        self.requests = []

    def generate(self, request, *, output_file: Path) -> GeneratedImage:
        self.requests.append(request)
        output_file.write_bytes(b"\xff\xd8\xff\xe0first-frame")
        return GeneratedImage(
            provider="test",
            model="test-image",
            request_id="image_001",
            path=output_file,
            media_type="image/jpeg",
        )


def test_renderer_submits_contract_prompt_not_stored_dialogue(tmp_path) -> None:
    provider = RecordingFailedProvider()
    renderer = HailuoVideoRenderer(provider, poll_interval_seconds=0)
    contract = KeyframeContract(
        character_appearances=["林辰：黑色短发，深灰宗门服"],
        start_keyframe="林辰持剑站在破碎石柱前。",
        action="林辰挥剑格挡玄兽利爪。",
        result="玄兽利爪被剑锋弹开。",
        transition_from_previous="承接上一镜，林辰已拔剑并面向玄兽。",
        transition_to_next="下一镜从利爪弹开、林辰站稳的画面继续。",
    )
    shot = make_shot(6).model_copy(
        update={
            "video_prompt": "玄兽低声说：你的兄长并没有死。",
            "keyframe_contract": contract,
        }
    )
    state_file = tmp_path / "render_state.json"

    with pytest.raises(MiniMaxMediaError, match="intentional test failure"):
        renderer._render_shot(
            shot,
            tmp_path,
            deadline=float("inf"),
            first_frame=None,
            state={"shots": {}},
            state_file=state_file,
        )

    submitted_prompt = provider.requests[0].prompt
    assert "你的兄长并没有死" not in submitted_prompt
    assert "唯一连续动作：林辰挥剑格挡玄兽利爪" in submitted_prompt


def test_renderer_uses_character_reference_when_making_scene_first_frame(tmp_path) -> None:
    reference = tmp_path / "character_reference.jpg"
    reference.write_bytes(b"\xff\xd8\xff\xe0reference")
    video_provider = RecordingFailedProvider()
    image_provider = RecordingImageProvider()
    renderer = HailuoVideoRenderer(
        video_provider,
        image_provider=image_provider,
        character_references={"char_001": reference},
        poll_interval_seconds=0,
    )

    with pytest.raises(MiniMaxMediaError, match="intentional test failure"):
        renderer._render_shot(
            make_shot(6),
            tmp_path,
            deadline=float("inf"),
            first_frame=None,
            state={"shots": {}},
            state_file=tmp_path / "render_state.json",
        )

    assert len(image_provider.requests) == 1
    assert image_provider.requests[0].reference_image == "data:image/jpeg;base64,/9j/4HJlZmVyZW5jZQ=="
