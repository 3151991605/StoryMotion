from __future__ import annotations

import math

from storymotion.models import KeyframeContract, ScreenplayPackage, Shot, ShotPackage


SHOT_TYPES = ("wide", "medium", "close_up", "over_shoulder", "close_up", "wide")
CAMERA_MOVEMENTS = (
    "slow_push",
    "tracking",
    "static",
    "slow_orbit",
    "handheld_subtle",
    "slow_push",
)
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
DEFAULT_NEGATIVE_PROMPT = (
    "文字、字幕、水印、标志、画面模糊、低细节、多余肢体、重复人物、"
    "脸部不一致、服装不一致、现代物品"
)


def _dramatic_effect(action: str, emotion: str) -> str:
    text = f"{action} {emotion}"
    if any(word in text for word in ("时间", "倒退", "回溯", "轮回")):
        return "破碎钟表倒影、逆向漂浮的尘埃、短暂的蓝色时间涟漪"
    if any(word in text for word in ("能力", "觉醒", "法术", "火", "魔", "异能")):
        return "受控的发光能量粒子环绕关键动作"
    if any(word in text for word in ("追", "逃", "危机", "攻击", "冲突")):
        return "疾风、扬尘、火花与明确的环境反应"
    return "克制的氛围粒子，以及对动作的明确环境反应"


def _action_beat(action: str, part_index: int, part_count: int) -> str:
    if part_count == 1:
        return f"完成一次不可重复的关键动作：{action}"
    if part_index == 0:
        return f"动作起点：角色进入画面、锁定目标并开始执行——{action}"
    if part_index == part_count - 1:
        return f"动作结果：{action} 的后果显现，角色停下并作出有信息量的反应"
    return f"动作升级：{action} 持续推进，环境与角色状态出现新的可见变化"


def _keyframe_contract(
    *,
    character_visuals: list[str],
    location_name: str,
    location_description: str,
    action: str,
    focus: str,
    emotion: str,
    part_index: int,
    part_count: int,
) -> KeyframeContract:
    required_visuals = [location_name, *character_visuals] or [location_name]
    if part_index == 0:
        opening_state = f"{location_name}中，动作发生前的紧张状态清晰可见。"
    else:
        opening_state = f"承接上一镜的动作进度，{focus}。"
    if part_index == part_count - 1:
        visible_result = f"{action} 的后果已经发生，角色呈现{emotion}反应。"
    else:
        visible_result = "动作推进后，人物或环境出现肉眼可见的新变化。"
    continuity_anchor = (
        f"场景固定为{location_name}（{location_description}）；"
        f"人物外观固定为{'；'.join(character_visuals) or '无可见人物'}。"
    )
    return KeyframeContract(
        character_appearances=required_visuals,
        start_keyframe=opening_state,
        action=focus,
        result=visible_result,
        transition_from_previous=(
            f"{continuity_anchor}本镜为场景开端。"
            if part_index == 0
            else f"{continuity_anchor}承接上一镜已经发生的动作进度。"
        ),
        transition_to_next=(
            f"{continuity_anchor}下一镜从以下可见状态继续：{visible_result}"
        ),
    )


class RuleShotProvider:
    def __init__(self, *, max_shot_duration: float = 10.0) -> None:
        if max_shot_duration <= 0:
            raise ValueError("max_shot_duration must be positive")
        self.max_shot_duration = float(max_shot_duration)

    def generate(self, screenplay: ScreenplayPackage) -> ShotPackage:
        characters = {character.id: character for character in screenplay.characters}
        locations = {location.id: location for location in screenplay.locations}
        shots: list[Shot] = []

        for scene in screenplay.scenes:
            part_count = math.ceil(scene.duration / self.max_shot_duration)
            remaining = float(scene.duration)
            dialogue_text = " ".join(
                f"{characters[dialogue.speaker_id].name}：{dialogue.text}"
                for dialogue in scene.dialogues
            )
            spoken_text = " ".join(
                text for text in (scene.voiceover or "", dialogue_text) if text
            )
            location = locations[scene.location_id]
            character_visuals = [
                f"{characters[character_id].name}：{characters[character_id].visual_prompt_zh}"
                for character_id in scene.characters
            ]

            for part_index in range(part_count):
                duration = min(self.max_shot_duration, remaining)
                remaining -= duration
                shot_index = len(shots)
                shot_type = SHOT_TYPES[shot_index % len(SHOT_TYPES)]
                camera_movement = CAMERA_MOVEMENTS[
                    shot_index % len(CAMERA_MOVEMENTS)
                ]
                part_label = f"第{part_index + 1}/{part_count}段"
                focus = _action_beat(scene.action, part_index, part_count)
                effect = _dramatic_effect(scene.action, scene.emotion)
                contract = _keyframe_contract(
                    character_visuals=character_visuals,
                    location_name=location.name,
                    location_description=location.visual_description,
                    action=scene.action,
                    focus=focus,
                    emotion=scene.emotion,
                    part_index=part_index,
                    part_count=part_count,
                )
                visual_description = (
                    f"{location.name}，{focus}，{part_label}，情绪：{scene.emotion}。"
                )
                image_prompt = (
                    "竖屏 9:16，中国动画短剧关键帧。"
                    f"人物与画面要素：{'；'.join(contract.character_appearances)}。"
                    f"起始关键帧：{contract.start_keyframe}"
                    f"关键动作：{contract.action}。"
                    f"结束关键帧：{contract.result}。"
                    f"承接上一镜：{contract.transition_from_previous}"
                    f"交给下一镜：{contract.transition_to_next}"
                    f"镜头：{SHOT_TYPE_LABELS[shot_type]}，"
                    f"{CAMERA_MOVEMENT_LABELS[camera_movement]}。特效：{effect}。"
                    "画面清晰，无屏幕文字、字幕或水印。"
                )
                video_prompt = (
                    "竖屏 9:16，高品质中国动画短剧。"
                    f"人物与画面要素：{'；'.join(contract.character_appearances)}。"
                    f"起始关键帧：{contract.start_keyframe}"
                    f"唯一连续动作：{contract.action}。"
                    f"结束关键帧：{contract.result}。"
                    f"镜头：{SHOT_TYPE_LABELS[shot_type]}，"
                    f"{CAMERA_MOVEMENT_LABELS[camera_movement]}。特效：{effect}。"
                    f"承接上一镜：{contract.transition_from_previous}"
                    f"交给下一镜：{contract.transition_to_next}"
                    "一个连续镜头，不循环、不重复动作、不随机切镜；"
                    "不出现文字、字幕、水印、口播或口型表演。"
                )
                audio_prompt = spoken_text or (
                    f"{location.name}环境声，情绪氛围：{scene.emotion}，无额外对白"
                )
                shots.append(
                    Shot(
                        shot_id=f"shot_{shot_index + 1:03d}",
                        scene_id=scene.scene_id,
                        duration=duration,
                        shot_type=shot_type,
                        camera_movement=camera_movement,
                        visual_description=visual_description,
                        character_ids=scene.characters,
                        image_prompt=image_prompt,
                        video_prompt=video_prompt,
                        keyframe_contract=contract,
                        negative_prompt=DEFAULT_NEGATIVE_PROMPT,
                        audio_prompt=audio_prompt,
                    )
                )

        return ShotPackage(
            title=screenplay.title,
            target_duration=screenplay.target_duration,
            shots=shots,
        )
