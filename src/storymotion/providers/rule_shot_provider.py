from __future__ import annotations

import math

from storymotion.models import ScreenplayPackage, Shot, ShotPackage


SHOT_TYPES = ("wide", "medium", "close_up", "over_shoulder", "close_up", "wide")
CAMERA_MOVEMENTS = (
    "slow_push",
    "tracking",
    "static",
    "slow_orbit",
    "handheld_subtle",
    "slow_push",
)
DEFAULT_NEGATIVE_PROMPT = (
    "text, subtitles, watermark, logo, blurry, low detail, extra limbs, "
    "duplicate character, inconsistent face, inconsistent costume, modern objects"
)


def _dramatic_effect(action: str, emotion: str) -> str:
    text = f"{action} {emotion}".lower()
    if any(word in text for word in ("时间", "倒退", "回溯", "轮回")):
        return "fractured clock reflections, reverse-moving dust, brief blue time-ripple VFX"
    if any(word in text for word in ("能力", "觉醒", "法术", "灵", "魔", "异能")):
        return "controlled luminous energy particles, light wrapping around the decisive gesture"
    if any(word in text for word in ("追", "逃", "危机", "攻击", "冲突")):
        return "dynamic wind, drifting dust, sparks and a sharp environmental reaction"
    return "subtle atmospheric particles and a clear visual reaction to the action"


def _action_beat(action: str, part_index: int, part_count: int) -> str:
    if part_count == 1:
        return f"一个完整且不可重复的关键动作：{action}"
    if part_index == 0:
        return f"动作起点：角色进入画面、锁定目标并开始执行——{action}"
    if part_index == part_count - 1:
        return f"动作结果：{action} 的后果显现，角色停下并作出有信息量的反应"
    return f"动作升级：{action} 持续推进，环境与角色状态出现新的可见变化"


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

            for part_index in range(part_count):
                duration = min(self.max_shot_duration, remaining)
                remaining -= duration
                shot_index = len(shots)
                shot_type = SHOT_TYPES[shot_index % len(SHOT_TYPES)]
                camera_movement = CAMERA_MOVEMENTS[
                    shot_index % len(CAMERA_MOVEMENTS)
                ]
                character_prompts = "; ".join(
                    characters[character_id].visual_prompt_en
                    for character_id in scene.characters
                )
                part_label = f"第{part_index + 1}/{part_count}段"
                focus = _action_beat(scene.action, part_index, part_count)
                if spoken_text:
                    focus += f"；在自然停顿中说出：{spoken_text}"
                effect = _dramatic_effect(scene.action, scene.emotion)
                visual_description = (
                    f"{location.name}，{focus}；{part_label}，情绪：{scene.emotion}。"
                )
                image_prompt = (
                    "vertical 9:16, premium Chinese anime short drama, consistent art direction, "
                    f"{shot_type} composition, {location.visual_description}; "
                    f"characters: {character_prompts or 'no visible character'}; "
                    f"action: {focus}; effects: {effect}; consistent character design, no on-screen text"
                )
                video_prompt = (
                    f"Vertical 9:16 premium Chinese anime drama, {shot_type} shot, "
                    f"camera: {camera_movement}. One continuous non-repeating action only: {focus}. "
                    "Start with a readable setup, build to one decisive change, end on a held reaction. "
                    f"Location: {location.name}, effects: {effect}. Preserve the exact faces, costumes, "
                    "props, lighting, spatial positions and art style from the supplied first frame. "
                    "No looping motion, no repeated gesture, no random cuts, no text, subtitles or watermark."
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
                        negative_prompt=DEFAULT_NEGATIVE_PROMPT,
                        audio_prompt=audio_prompt,
                    )
                )

        return ShotPackage(
            title=screenplay.title,
            target_duration=screenplay.target_duration,
            shots=shots,
        )
