"""Render keyframe contracts into concise Chinese-first media prompts."""

from __future__ import annotations

from storymotion.models import KeyframeContract, ScreenplayPackage, Shot, ShotPackage, StoryPackage

SHOT_TYPE_LABELS = {
    "wide": "全景",
    "medium": "中景",
    "close_up": "特写",
    "over_shoulder": "过肩镜头",
}
CAMERA_MOVEMENT_LABELS = {
    "slow_push": "缓慢推进",
    "tracking": "跟拍",
    "static": "固定镜头",
    "slow_orbit": "缓慢环绕",
    "handheld_subtle": "轻微手持",
}


def _chinese_camera_term(value: str, labels: dict[str, str]) -> str:
    return labels.get(value, value)


def _render_image_prompt(contract: KeyframeContract, *, shot_type: str, camera: str) -> str:
    return (
        "竖屏 9:16，中国动画短剧关键帧。"
        f"人物与画面要素：{'；'.join(contract.character_appearances)}。"
        f"起始关键帧：{contract.start_keyframe}"
        f"关键动作：{contract.action}。"
        f"结束关键帧：{contract.result}。"
        f"承接上一镜：{contract.transition_from_previous}"
        f"交给下一镜：{contract.transition_to_next}"
        f"镜头：{_chinese_camera_term(shot_type, SHOT_TYPE_LABELS)}，"
        f"{_chinese_camera_term(camera, CAMERA_MOVEMENT_LABELS)}。"
        "画面清晰、因果关系明确；无文字、字幕、水印、标志。"
    )[:4900]


def _render_video_prompt(contract: KeyframeContract, *, shot_type: str, camera: str) -> str:
    return (
        "竖屏 9:16，高品质中国动画短剧。"
        f"人物与画面要素：{'；'.join(contract.character_appearances)}。"
        f"起始关键帧：{contract.start_keyframe}"
        f"唯一连续动作：{contract.action}。"
        f"结束关键帧：{contract.result}。"
        f"镜头：{_chinese_camera_term(shot_type, SHOT_TYPE_LABELS)}，"
        f"{_chinese_camera_term(camera, CAMERA_MOVEMENT_LABELS)}。"
        f"承接上一镜：{contract.transition_from_previous}"
        f"交给下一镜：{contract.transition_to_next}"
        "一个连续镜头，动作必须从开场推进到可见结果；"
        "不循环、不重复动作、不随机切镜；"
        "无文字、字幕、水印、口播或口型表演。"
    )[:4900]


def render_video_prompt_for_shot(shot: Shot) -> str:
    """Build the only prompt that may be submitted to a video provider.

    Stored prompts are presentation artifacts and can originate from legacy
    JSON or third-party adapters.  The provider boundary instead uses the
    visual contract, which deliberately has no dialogue or narration fields.
    """
    return _render_video_prompt(
        shot.keyframe_contract,
        shot_type=shot.shot_type,
        camera=shot.camera_movement,
    )


def direct_storyboard(
    story: StoryPackage, screenplay: ScreenplayPackage, storyboard: ShotPackage
) -> ShotPackage:
    """Use one observable contract as the source of truth for every visual prompt."""
    del story, screenplay
    return storyboard.model_copy(
        update={
            "shots": [
                shot.model_copy(
                    update={
                        "image_prompt": _render_image_prompt(
                            shot.keyframe_contract,
                            shot_type=shot.shot_type,
                            camera=shot.camera_movement,
                        ),
                        "video_prompt": render_video_prompt_for_shot(shot),
                    }
                )
                for shot in storyboard.shots
            ]
        }
    )
