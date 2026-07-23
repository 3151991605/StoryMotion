from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from pydantic import ValidationError

from storymotion.models import StoryMotionBundle


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json"


@pytest.fixture
def valid_bundle_data() -> dict:
    characters = [
        {
            "id": "char_001",
            "name": "林辰",
            "role": "protagonist",
            "age": 18,
            "personality": ["冷静", "执着"],
            "goal": "查明兄长失踪真相",
            "ability": "每天让时间倒退十秒",
            "appearance": {
                "hair": "黑色短发",
                "clothing": "深灰色宗门服",
                "distinctive_features": ["左眼下方浅色伤痕"],
            },
            "visual_prompt_zh": "黑色短发少年，深灰宗门服，左眼下浅色伤痕",
            "visual_prompt_en": "black-haired young man in a dark gray sect robe",
        },
        {
            "id": "char_002",
            "name": "玄兽",
            "role": "antagonist",
            "age": None,
            "personality": ["危险", "神秘"],
            "goal": "逼迫林辰使用时间能力",
            "ability": None,
            "appearance": {
                "hair": "无",
                "clothing": "黑色鳞甲",
                "distinctive_features": ["金色竖瞳"],
            },
            "visual_prompt_zh": "黑色鳞甲玄兽，金色竖瞳",
            "visual_prompt_en": "black-scaled beast with golden slit pupils",
        },
    ]
    locations = [
        {
            "id": "loc_001",
            "name": "废弃试炼塔",
            "visual_description": "破碎石柱与蓝色月光",
        }
    ]
    scenes = [
        {
            "scene_id": "scene_001",
            "location_id": "loc_001",
            "duration": 30,
            "characters": ["char_001", "char_002"],
            "scene_goal": "展示时间回溯能力",
            "action": "玄兽利爪落下，画面突然倒放十秒。",
            "dialogues": [],
            "voiceover": "死亡到来的瞬间，时间倒退了。",
            "emotion": "震惊",
            "transition": "flash",
        },
        {
            "scene_id": "scene_002",
            "location_id": "loc_001",
            "duration": 30,
            "characters": ["char_001", "char_002"],
            "scene_goal": "制造悬念",
            "action": "玄兽停下攻击，金色竖瞳盯住林辰。",
            "dialogues": [
                {
                    "speaker_id": "char_002",
                    "text": "你的兄长并没有死。",
                    "emotion": "低沉",
                }
            ],
            "voiceover": None,
            "emotion": "悬疑",
            "transition": None,
        },
    ]
    return {
        "brief": {
            "genre": "东方玄幻",
            "style": ["热血", "悬疑"],
            "protagonist_name": "林辰",
            "core_idea": "主角每天可以让时间倒退十秒",
            "target_duration": 60,
            "max_characters": 3,
            "max_locations": 5,
            "ending_type": "cliffhanger",
        },
        "story": {
            "title": "倒退十秒",
            "logline": "林辰在死亡瞬间觉醒回溯能力，并得知兄长可能尚在人世。",
            "target_duration": 60,
            "worldview": {
                "world_name": "九域",
                "era": "宗门统治时代",
                "power_system": "灵脉修炼",
                "special_rule": "时间能力会引发反噬",
                "locations": locations,
            },
            "characters": characters,
            "beats": [
                {"beat_type": "hook", "duration": 10, "content": "死亡瞬间时间倒退"},
                {"beat_type": "setup", "duration": 10, "content": "林辰意识到能力觉醒"},
                {"beat_type": "conflict", "duration": 20, "content": "连续回溯躲避玄兽"},
                {"beat_type": "reversal", "duration": 10, "content": "玄兽突然停止攻击"},
                {"beat_type": "cliffhanger", "duration": 10, "content": "兄长可能没有死"},
            ],
            "story_text": "林辰在废弃试炼塔中遭到玄兽袭击。死亡瞬间，时间突然倒退十秒。他连续回溯躲开利爪，却发现手背出现黑色裂纹。玄兽最终停下攻击，告诉他失踪的兄长并没有死。",
        },
        "screenplay": {
            "title": "倒退十秒",
            "target_duration": 60,
            "characters": characters,
            "locations": locations,
            "scenes": scenes,
        },
        "storyboard": {
            "title": "倒退十秒",
            "target_duration": 60,
            "shots": [
                {
                    "shot_id": "shot_001",
                    "scene_id": "scene_001",
                    "duration": 30,
                    "shot_type": "medium",
                    "camera_movement": "tracking",
                    "visual_description": "玄兽利爪逼近林辰，画面高速倒放。",
                    "character_ids": ["char_001", "char_002"],
                    "image_prompt": "废弃石塔中的黑发少年与黑色玄兽",
                    "video_prompt": "利爪落下后环境倒放，角色外观保持一致",
                    "negative_prompt": "文字，水印，多余肢体",
                    "audio_prompt": "风声与倒放音效",
                },
                {
                    "shot_id": "shot_002",
                    "scene_id": "scene_002",
                    "duration": 30,
                    "shot_type": "close_up",
                    "camera_movement": "slow_push",
                    "visual_description": "玄兽金色竖瞳特写，林辰震惊回头。",
                    "character_ids": ["char_001", "char_002"],
                    "image_prompt": "金色竖瞳玄兽与震惊少年",
                    "video_prompt": "镜头缓慢推进，玄兽低声说出秘密",
                    "negative_prompt": None,
                    "audio_prompt": "低沉对白与环境风声",
                },
            ],
        },
    }


def test_valid_bundle_parses(valid_bundle_data: dict) -> None:
    bundle = StoryMotionBundle.model_validate(valid_bundle_data)
    assert bundle.brief.protagonist_name == "林辰"
    assert bundle.storyboard.total_shot_duration == 60


def test_unknown_fields_are_rejected(valid_bundle_data: dict) -> None:
    data = deepcopy(valid_bundle_data)
    data["brief"]["unexpected"] = True
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        StoryMotionBundle.model_validate(data)


def test_numeric_strings_are_rejected(valid_bundle_data: dict) -> None:
    data = deepcopy(valid_bundle_data)
    data["brief"]["target_duration"] = "60"
    with pytest.raises(ValidationError, match="valid integer"):
        StoryMotionBundle.model_validate(data)


def test_story_beat_duration_must_match_target(valid_bundle_data: dict) -> None:
    data = deepcopy(valid_bundle_data)
    data["story"]["beats"][0]["duration"] = 9
    with pytest.raises(ValidationError, match="plot beat duration"):
        StoryMotionBundle.model_validate(data)


def test_story_beats_must_follow_canonical_order(valid_bundle_data: dict) -> None:
    data = deepcopy(valid_bundle_data)
    data["story"]["beats"][0], data["story"]["beats"][1] = (
        data["story"]["beats"][1],
        data["story"]["beats"][0],
    )
    with pytest.raises(ValidationError, match="canonical order"):
        StoryMotionBundle.model_validate(data)


def test_scene_character_reference_must_exist(valid_bundle_data: dict) -> None:
    data = deepcopy(valid_bundle_data)
    data["screenplay"]["scenes"][0]["characters"] = ["char_missing"]
    with pytest.raises(ValidationError, match="unknown character"):
        StoryMotionBundle.model_validate(data)


def test_shot_scene_reference_must_exist(valid_bundle_data: dict) -> None:
    data = deepcopy(valid_bundle_data)
    data["storyboard"]["shots"][0]["scene_id"] = "scene_missing"
    with pytest.raises(ValidationError, match="unknown screenplay scene"):
        StoryMotionBundle.model_validate(data)


def test_brief_limits_are_enforced_across_layers(valid_bundle_data: dict) -> None:
    data = deepcopy(valid_bundle_data)
    data["brief"]["max_characters"] = 1
    with pytest.raises(ValidationError, match="character limit"):
        StoryMotionBundle.model_validate(data)


def test_character_free_establishing_shot_is_allowed(valid_bundle_data: dict) -> None:
    data = deepcopy(valid_bundle_data)
    data["screenplay"]["scenes"][0]["characters"] = []
    data["storyboard"]["shots"][0]["character_ids"] = []
    bundle = StoryMotionBundle.model_validate(data)
    assert bundle.storyboard.shots[0].character_ids == []


def test_prop_contract_is_validated_across_story_scene_and_shot(
    valid_bundle_data: dict,
) -> None:
    data = deepcopy(valid_bundle_data)
    prop = {
        "id": "prop_001",
        "name": "裂纹手机",
        "visual_description": "黑色窄边手机，透明磨损保护壳，背面左上双摄",
        "continuity_features": ["黑色机身", "透明保护壳", "左上双摄"],
        "aliases": ["手机", "电话"],
    }
    data["story"]["props"] = [prop]
    data["screenplay"]["props"] = [prop]
    data["screenplay"]["scenes"][0]["prop_ids"] = ["prop_001"]
    data["storyboard"]["shots"][0]["prop_ids"] = ["prop_001"]

    bundle = StoryMotionBundle.model_validate(data)

    assert bundle.story.props[0].name == "裂纹手机"
    assert bundle.screenplay.scenes[0].prop_ids == ["prop_001"]
    assert bundle.storyboard.shots[0].prop_ids == ["prop_001"]


def test_unknown_shot_prop_reference_is_rejected(valid_bundle_data: dict) -> None:
    data = deepcopy(valid_bundle_data)
    data["storyboard"]["shots"][0]["prop_ids"] = ["prop_missing"]
    with pytest.raises(ValidationError, match="unknown prop"):
        StoryMotionBundle.model_validate(data)


def test_json_fixture_round_trip() -> None:
    bundle = StoryMotionBundle.model_validate_json(
        FIXTURE_PATH.read_text(encoding="utf-8")
    )
    serialized = bundle.model_dump_json()
    restored = StoryMotionBundle.model_validate_json(serialized)
    assert restored == bundle
