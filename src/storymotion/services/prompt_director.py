"""Render visual-only shot contracts into media prompts."""

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

# This is deliberately part of every video prompt rather than an optional
# provider parameter: the supported video API has no separate negative-prompt
# field. Keep character, anatomy and presentation failures together so they
# cannot drift between storyboard implementations.
VIDEO_NEGATIVE_CONSTRAINTS = (
    "负面约束：禁止换脸，禁止改变人物年龄、性别表达、发型、服装颜色或服装层次；"
    "禁止新增人物、角色复制、角色融合或背景人物抢镜；"
    "禁止多余手指、手指融合、肢体缺失或身体变形；"
    "禁止改变关键道具；禁止文字、字幕、水印、标志、旁白和说话口型；"
    "禁止随机切镜。"
)


def _chinese_camera_term(value: str, labels: dict[str, str]) -> str:
    return labels.get(value, value)


def _render_image_prompt(
    contract: KeyframeContract, *, shot_type: str, camera: str, identity_contract: str
) -> str:
    return (
        f"{identity_contract} "
        "竖屏 9:16，中国二维动画短剧关键帧。"
        f"人物与画面要素：{'；'.join(contract.character_appearances)}。"
        f"起始关键帧：{contract.start_keyframe}。"
        f"关键动作：{contract.action}。"
        f"结束关键帧：{contract.result}。"
        f"承接上一镜：{contract.transition_from_previous}。"
        f"交给下一镜：{contract.transition_to_next}。"
        f"镜头：{_chinese_camera_term(shot_type, SHOT_TYPE_LABELS)}，"
        f"{_chinese_camera_term(camera, CAMERA_MOVEMENT_LABELS)}。"
        "画面清晰、因果关系明确；无文字、字幕、水印、标志。"
    )[:4900]


def _render_video_prompt(
    contract: KeyframeContract,
    *,
    shot_type: str,
    camera: str,
    identity_contract: str = "",
    duration: float = 6,
) -> str:
    """Render the only prompt allowed across the video-provider boundary."""
    prompt = (
        "图生视频，竖屏 9:16，2D 动画短剧，赛璐璐上色、干净线稿、受控平涂色彩；"
        "绝不写实或真人风格。"
        "identity lock：以输入首帧作为第 0 秒画面，不改变人物身份、脸部、发型、服装、"
        "道具、场景、色调和画风。"
        f" {identity_contract}"
        f"人物与画面要素：{'；'.join(contract.character_appearances)}。"
        f"起始关键帧：{contract.start_keyframe}。"
        f"spatial layout：前景、中景、背景关系保持与首帧一致；"
        f"承接上一镜：{contract.transition_from_previous}。"
        f"镜头：{_chinese_camera_term(shot_type, SHOT_TYPE_LABELS)}，"
        f"{_chinese_camera_term(camera, CAMERA_MOVEMENT_LABELS)}，全程一个连续镜头。"
        f"time sequence（约 {duration:g} 秒）：先保持起始构图并让环境轻微自然运动；"
        f"然后执行唯一连续动作：{contract.action}；"
        f"最后停在结束关键帧／可见结果：{contract.result}。"
        f"连续性：交给下一镜：{contract.transition_to_next}。"
        "动作从起点推进到结果，不循环、不重复。"
        f"{VIDEO_NEGATIVE_CONSTRAINTS}"
    )
    # Preserve the complete negative contract even for unusually long
    # storyboard descriptions, which otherwise would truncate the final rule.
    if len(prompt) <= 4900:
        return prompt
    return prompt[: 4900 - len(VIDEO_NEGATIVE_CONSTRAINTS)] + VIDEO_NEGATIVE_CONSTRAINTS


def render_video_prompt_for_shot(shot: Shot) -> str:
    """Rebuild a provider prompt from the visual contract, never stored prose."""
    return _render_video_prompt(
        shot.keyframe_contract,
        shot_type=shot.shot_type,
        camera=shot.camera_movement,
        identity_contract=shot.identity_contract,
        duration=shot.duration,
    )


def direct_storyboard(
    story: StoryPackage, screenplay: ScreenplayPackage, storyboard: ShotPackage
) -> ShotPackage:
    """Use one observable contract as the source of truth for every visual prompt."""
    del screenplay
    characters = {character.id: character for character in story.characters}
    directed_shots = []
    for shot in storyboard.shots:
        identity_contract = _shot_identity_contract(shot.character_ids, characters)
        directed_shots.append(
            shot.model_copy(
                update={
                    "identity_contract": identity_contract,
                    "image_prompt": _render_image_prompt(
                        shot.keyframe_contract,
                        shot_type=shot.shot_type,
                        camera=shot.camera_movement,
                        identity_contract=identity_contract,
                    ),
                    "video_prompt": _render_video_prompt(
                        shot.keyframe_contract,
                        shot_type=shot.shot_type,
                        camera=shot.camera_movement,
                        identity_contract=identity_contract,
                        duration=shot.duration,
                    ),
                }
            )
        )
    return storyboard.model_copy(update={"shots": directed_shots})


def _shot_identity_contract(character_ids: list[str], characters: dict[str, object]) -> str:
    """Keep all characters explicit; the first listed character is the anchor authority."""
    if not character_ids:
        return (
            "STYLE LOCK: keep the supplied keyframe's 2D cel-shaded linework, palette, "
            "setting and composition unchanged; do not introduce people."
        )
    entries = []
    for position, character_id in enumerate(character_ids):
        character = characters[character_id]
        appearance = character.appearance
        features = "; ".join(appearance.distinctive_features) or "anchor-defined details"
        authority = "PRIMARY ANCHOR AUTHORITY" if position == 0 else "SECONDARY CAST LOCK"
        entries.append(
            f"{authority}: {character.name}; hair={appearance.hair}; wardrobe={appearance.clothing}; "
            f"signature={features}; canonical={character.visual_prompt_zh}."
        )
    return (
        " IMMUTABLE CHARACTER CONTRACT: "
        + " ".join(entries)
        + " Do not change or add face details, eye colour, hairstyle, body proportions, age, "
        "gender presentation, wardrobe layers, hats, glasses, jewellery, weapons, gloves or bags."
    )
