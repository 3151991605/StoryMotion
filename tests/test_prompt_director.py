from pathlib import Path

from storymotion.models import StoryMotionBundle
from storymotion.services import direct_storyboard


def test_renders_every_video_prompt_from_an_observable_keyframe_contract() -> None:
    fixture = Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json"
    bundle = StoryMotionBundle.model_validate_json(fixture.read_text(encoding="utf-8"))
    directed = direct_storyboard(bundle.story, bundle.screenplay, bundle.storyboard)

    assert all("必须出现" in shot.video_prompt for shot in directed.shots)
    assert all("唯一连续动作" in shot.video_prompt for shot in directed.shots)
    assert all("可见结果" in shot.video_prompt for shot in directed.shots)
    assert all("无文字、字幕、水印" in shot.image_prompt for shot in directed.shots)
    assert all("Vertical" not in shot.video_prompt for shot in directed.shots)
