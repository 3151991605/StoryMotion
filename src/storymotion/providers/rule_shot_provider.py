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
                focus = (
                    scene.action
                    if part_index == 0 or not spoken_text
                    else f"角色保持动作连续并完成对白：{spoken_text}"
                )
                visual_description = (
                    f"{location.name}，{focus}；{part_label}，情绪：{scene.emotion}。"
                )
                image_prompt = (
                    "vertical 9:16, oriental fantasy anime, cinematic lighting, "
                    f"{shot_type} composition, {location.visual_description}; "
                    f"characters: {character_prompts or 'no visible character'}; "
                    f"action: {focus}; consistent character design, no on-screen text"
                )
                video_prompt = (
                    f"{duration:g}-second vertical 9:16 anime shot, {shot_type}, "
                    f"camera movement: {camera_movement}. {focus}. "
                    f"Location remains {location.name}. Preserve character faces, "
                    "clothing, props, spatial continuity and lighting across shots."
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
