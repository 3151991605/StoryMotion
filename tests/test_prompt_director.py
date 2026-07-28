from pathlib import Path

from storymotion.models import StoryMotionBundle
from storymotion.services import direct_storyboard, render_video_prompt_for_shot
from storymotion.services.prompt_director import VIDEO_NEGATIVE_CONSTRAINTS


def test_renders_every_video_prompt_from_an_observable_keyframe_contract() -> None:
    fixture = Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json"
    bundle = StoryMotionBundle.model_validate_json(fixture.read_text(encoding="utf-8"))
    directed = direct_storyboard(bundle.story, bundle.screenplay, bundle.storyboard)

    assert all("人物与画面要素" in shot.video_prompt for shot in directed.shots)
    assert all("唯一连续动作" in shot.video_prompt for shot in directed.shots)
    assert all("结束关键帧" in shot.video_prompt for shot in directed.shots)
    assert all("承接上一镜" in shot.video_prompt for shot in directed.shots)
    assert all("交给下一镜" in shot.video_prompt for shot in directed.shots)
    assert all("无文字、字幕、水印" in shot.image_prompt for shot in directed.shots)
    assert all("Vertical" not in shot.video_prompt for shot in directed.shots)
    assert all("time sequence" in shot.video_prompt for shot in directed.shots)
    assert all("identity lock" in shot.video_prompt for shot in directed.shots)
    assert all("spatial layout" in shot.video_prompt for shot in directed.shots)
    assert all("IMMUTABLE CHARACTER CONTRACT" in shot.video_prompt for shot in directed.shots)
    assert all("PRIMARY ANCHOR AUTHORITY" in shot.video_prompt for shot in directed.shots)
    assert all(VIDEO_NEGATIVE_CONSTRAINTS in shot.video_prompt for shot in directed.shots)

    # The provider boundary rebuilds prompts from structured fields.  Identity
    # must survive that rebuild instead of existing only in saved prompt prose.
    assert all(
        "IMMUTABLE CHARACTER CONTRACT" in render_video_prompt_for_shot(shot)
        for shot in directed.shots
    )
    assert all(
        VIDEO_NEGATIVE_CONSTRAINTS in render_video_prompt_for_shot(shot)
        for shot in directed.shots
    )
