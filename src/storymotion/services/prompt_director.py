"""Render keyframe contracts into concise Chinese-first media prompts."""

from __future__ import annotations

from storymotion.models import KeyframeContract, ScreenplayPackage, ShotPackage, StoryPackage

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
        f"必须出现：{'；'.join(contract.required_visuals)}。"
        f"开场状态：{contract.opening_state}"
        f"关键动作：{contract.key_action}。"
        f"可见结果：{contract.visible_result}。"
        f"连续性：{contract.continuity_anchor}"
        f"镜头：{_chinese_camera_term(shot_type, SHOT_TYPE_LABELS)}，"
        f"{_chinese_camera_term(camera, CAMERA_MOVEMENT_LABELS)}。"
        "画面清晰、因果关系明确；无文字、字幕、水印、标志。"
    )[:4900]


def _render_video_prompt(contract: KeyframeContract, *, shot_type: str, camera: str) -> str:
    return (
        "竖屏 9:16，高品质中国动画短剧。"
        f"必须出现：{'；'.join(contract.required_visuals)}。"
        f"开场状态：{contract.opening_state}"
        f"唯一连续动作：{contract.key_action}。"
        f"可见结果：{contract.visible_result}。"
        f"镜头：{_chinese_camera_term(shot_type, SHOT_TYPE_LABELS)}，"
        f"{_chinese_camera_term(camera, CAMERA_MOVEMENT_LABELS)}。"
        f"连续性：{contract.continuity_anchor}"
        "一个连续镜头，动作必须从开场推进到可见结果；"
        "不循环、不重复动作、不随机切镜；"
        "无文字、字幕、水印、口播或口型表演。"
    )[:4900]


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
                        "video_prompt": _render_video_prompt(
                            shot.keyframe_contract,
                            shot_type=shot.shot_type,
                            camera=shot.camera_movement,
                        ),
                    }
                )
                for shot in storyboard.shots
            ]
        }
    )
