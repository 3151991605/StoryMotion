from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from storymotion.models import KeyframeContract, ScreenplayPackage, Shot, ShotPackage


class RawAudioPrompt(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    prompt: str = Field(min_length=1)


class RawPenShotFragment(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    fragment_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    negative_prompt: str | None = None
    duration: float = Field(gt=0, le=60)
    model: str | None = None
    style: str | None = None
    audio_prompt: RawAudioPrompt | None = None


class RawPenShotResult(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    fragments: list[RawPenShotFragment]


def screenplay_to_penshot_text(screenplay: ScreenplayPackage) -> str:
    lines = [f"标题：{screenplay.title}", f"总时长：{screenplay.target_duration}秒"]
    lines.append("角色：")
    for character in screenplay.characters:
        features = "、".join(character.appearance.distinctive_features)
        lines.append(
            f"- {character.id} {character.name}：{character.role}；"
            f"外观：{character.appearance.hair}，{character.appearance.clothing}，{features}"
        )
    lines.append("地点：")
    for location in screenplay.locations:
        lines.append(
            f"- {location.id} {location.name}：{location.visual_description}"
        )
    lines.append("分场剧本：")
    for scene in screenplay.scenes:
        lines.append(
            f"[{scene.scene_id}] 地点={scene.location_id} 时长={scene.duration}秒 "
            f"角色={','.join(scene.characters)} 情绪={scene.emotion}"
        )
        lines.append(f"动作：{scene.action}")
        for dialogue in scene.dialogues:
            lines.append(
                f"对白（{dialogue.speaker_id}，{dialogue.emotion or '中性'}）："
                f"{dialogue.text}"
            )
        if scene.voiceover:
            lines.append(f"旁白：{scene.voiceover}")
    return "\n".join(lines)


def _unwrap_result(raw_result: dict[str, Any]) -> dict[str, Any]:
    data = raw_result.get("data")
    return data if isinstance(data, dict) else raw_result


def _shot_type(prompt: str) -> str:
    lowered = prompt.lower()
    for needle, value in (
        ("close-up", "close_up"),
        ("close up", "close_up"),
        ("wide shot", "wide"),
        ("medium", "medium"),
        ("over-the-shoulder", "over_shoulder"),
    ):
        if needle in lowered:
            return value
    return "cinematic"


def _camera_movement(prompt: str) -> str:
    lowered = prompt.lower()
    for needle, value in (
        ("tracking", "tracking"),
        ("push-in", "slow_push"),
        ("push in", "slow_push"),
        ("pan ", "pan"),
        ("tilt ", "tilt"),
        ("zoom", "zoom"),
    ):
        if needle in lowered:
            return value
    return "static_or_unspecified"


def adapt_penshot_result(
    raw_result: dict[str, Any],
    screenplay: ScreenplayPackage,
) -> ShotPackage:
    parsed = RawPenShotResult.model_validate(_unwrap_result(raw_result))
    if not 5 <= len(parsed.fragments) <= 10:
        raise ValueError(
            f"MVP requires 5-10 fragments; got {len(parsed.fragments)}"
        )

    raw_total = sum(fragment.duration for fragment in parsed.fragments)
    if abs(raw_total - screenplay.target_duration) > 0.01:
        raise ValueError(
            "PenShot fragment duration must equal screenplay duration: "
            f"{raw_total} != {screenplay.target_duration}"
        )

    shots: list[Shot] = []
    locations = {location.id: location for location in screenplay.locations}
    scene_index = 0
    elapsed_in_scene = 0.0
    tolerance = 0.01
    for index, fragment in enumerate(parsed.fragments, start=1):
        if scene_index >= len(screenplay.scenes):
            raise ValueError("PenShot returned fragments beyond the final scene")
        scene = screenplay.scenes[scene_index]
        remaining = scene.duration - elapsed_in_scene
        if fragment.duration - remaining > tolerance:
            raise ValueError(
                f"fragment {fragment.fragment_id} crosses scene boundary "
                f"{scene.scene_id}: {fragment.duration} > {remaining}"
            )

        audio_prompt = (
            fragment.audio_prompt.prompt if fragment.audio_prompt is not None else None
        )
        shots.append(
            Shot(
                shot_id=f"shot_{index:03d}",
                scene_id=scene.scene_id,
                duration=fragment.duration,
                shot_type=_shot_type(fragment.prompt),
                camera_movement=_camera_movement(fragment.prompt),
                visual_description=fragment.prompt,
                character_ids=scene.characters,
                image_prompt=fragment.prompt,
                video_prompt=fragment.prompt,
                keyframe_contract=KeyframeContract(
                    character_appearances=[locations[scene.location_id].name],
                    start_keyframe=fragment.prompt,
                    action=scene.action,
                    result=f"{scene.action} 的结果在画面中清晰可见。",
                    transition_from_previous=(
                        f"保持{locations[scene.location_id].name}内的人物、服装、场景和光线一致。"
                    ),
                    transition_to_next=(
                        f"保持{locations[scene.location_id].name}内的人物、服装、场景和光线一致；"
                        "下一镜从动作结果继续。"
                    ),
                ),
                negative_prompt=fragment.negative_prompt,
                audio_prompt=audio_prompt,
            )
        )

        elapsed_in_scene += fragment.duration
        if abs(elapsed_in_scene - scene.duration) <= tolerance:
            scene_index += 1
            elapsed_in_scene = 0.0

    if scene_index != len(screenplay.scenes) or abs(elapsed_in_scene) > tolerance:
        raise ValueError("PenShot fragments did not cover every screenplay scene")

    return ShotPackage(
        title=screenplay.title,
        target_duration=screenplay.target_duration,
        shots=shots,
    )
