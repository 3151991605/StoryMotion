"""Generate validated story and screenplay packages from a short brief."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from json_repair import repair_json
from pydantic import ValidationError

from storymotion.models import ProjectBrief, ScreenplayPackage, StoryPackage
from storymotion.providers.openai_compatible import ChatClient, TextGenerationError


SYSTEM_PROMPT = """你是 StoryMotion 的中文漫剧编剧。只输出一个 JSON 对象，绝不输出 Markdown 或解释。
输出格式必须是 {"story": {...}, "screenplay": {"scenes": [...]}}。story 必须符合用户提供的 JSON Schema。screenplay 只需要输出 scenes，系统会自动从 story 继承标题、时长、人物和地点。
硬性规则：story.beats 的顺序固定为 hook、setup、conflict、reversal、cliffhanger，时长和 target_duration 精确相等；主角姓名必须出现。story.props 只列出会重复出现或承担剧情信息的关键道具，并固定外观细节；普通桌椅不要列入。每个 scene 使用 scene_id、location_id、duration、characters、prop_ids、scene_goal、action、dialogues、voiceover、emotion、transition。文本使用中文。"""


COMMON_PROP_CATALOG = (
    (
        "手机",
        ("手机", "智能手机", "电话"),
        "剧情专用手机，固定机身颜色、保护壳材质、摄像头布局、边框和磨损位置",
        ("机身颜色固定", "保护壳固定", "摄像头布局固定", "屏幕边框固定"),
    ),
    (
        "信件",
        ("信件", "信封", "纸条"),
        "剧情关键信件，固定纸张颜色、折痕、封口和边角磨损，不呈现可读文字",
        ("纸张颜色固定", "折痕固定", "封口样式固定"),
    ),
    (
        "照片",
        ("照片", "相片"),
        "剧情关键照片，固定尺寸、边框、色调、折角和表面损伤",
        ("边框固定", "折角固定", "表面损伤固定"),
    ),
    (
        "钥匙",
        ("钥匙", "钥匙串"),
        "剧情关键钥匙，固定材质、齿形、钥匙环和挂件",
        ("材质固定", "齿形固定", "挂件固定"),
    ),
    (
        "证件",
        ("证件", "警官证", "工作证", "徽章"),
        "剧情关键证件，固定外壳颜色、徽记位置和尺寸，不呈现可读文字",
        ("外壳固定", "徽记位置固定", "尺寸固定"),
    ),
    (
        "刀",
        ("刀", "匕首", "短刀"),
        "剧情关键刀具，固定刀身轮廓、护手、刀柄缠绕和磨损",
        ("刀身轮廓固定", "护手固定", "刀柄固定"),
    ),
    (
        "枪",
        ("手枪", "枪械", "枪"),
        "剧情关键枪械，固定轮廓、颜色、握把和表面磨损",
        ("轮廓固定", "颜色固定", "握把固定"),
    ),
    (
        "药瓶",
        ("药瓶", "药盒", "药剂"),
        "剧情关键药品容器，固定瓶形、瓶盖颜色、材质和标签色块，不呈现可读文字",
        ("瓶形固定", "瓶盖固定", "标签色块固定"),
    ),
    (
        "项链",
        ("项链", "吊坠"),
        "剧情关键项链，固定链条材质、吊坠轮廓、宝石颜色和刻痕",
        ("吊坠轮廓固定", "宝石颜色固定", "链条固定"),
    ),
    (
        "戒指",
        ("戒指", "指环"),
        "剧情关键戒指，固定材质、宽度、镶嵌物和刻纹",
        ("材质固定", "镶嵌物固定", "刻纹固定"),
    ),
    (
        "手表",
        ("手表", "腕表"),
        "剧情关键手表，固定表盘、表带、刻度布局和磨损",
        ("表盘固定", "表带固定", "刻度布局固定"),
    ),
    (
        "雨伞",
        ("雨伞", "伞"),
        "剧情关键雨伞，固定伞面颜色、伞柄、骨架和破损位置",
        ("伞面固定", "伞柄固定", "破损位置固定"),
    ),
)


@dataclass(frozen=True)
class NarrativeResult:
    story: StoryPackage
    screenplay: ScreenplayPackage


class NarrativeGenerator:
    MAX_ATTEMPTS = 3

    def __init__(self, client: ChatClient) -> None:
        self.client = client

    def generate(self, brief: ProjectBrief) -> NarrativeResult:
        user = (
            "根据 brief 创作一集可直接制作的竖屏 AI 漫剧。\n"
            f"brief={brief.model_dump_json()}\n"
            "story JSON Schema="
            f"{json.dumps(StoryPackage.model_json_schema(), ensure_ascii=False)}\n"
            "screenplay 示例结构：{\"scenes\":[{\"scene_id\":\"scene_001\",\"location_id\":\"loc_001\",\"duration\":15,\"characters\":[\"char_001\"],\"prop_ids\":[\"prop_001\"],\"scene_goal\":\"...\",\"action\":\"...\",\"dialogues\":[],\"voiceover\":null,\"emotion\":\"紧张\",\"transition\":null}]}"
        )
        prompt = user
        last_error: TextGenerationError | None = None
        for attempt in range(self.MAX_ATTEMPTS):
            content = self.client.complete(system=SYSTEM_PROMPT, user=prompt)
            try:
                return self._validate(content, brief)
            except TextGenerationError as error:
                last_error = error
                if attempt == self.MAX_ATTEMPTS - 1:
                    break
                prompt = (
                    "下面候选 JSON 未通过协议校验。只输出修复后的完整 JSON 对象，"
                    "不要 Markdown 或解释。最外层必须是包含 story 和 screenplay 的单个对象 {}，"
                    "禁止使用顶层数组 []、包装键或输出多个候选。"
                    "逐项修复所有时长、ID、跨层引用和 JSON 语法问题。\n"
                    f"校验错误：{error}\n候选 JSON：{content}"
                )
        raise TextGenerationError(
            f"text model output remained invalid after {self.MAX_ATTEMPTS} attempts: {last_error}"
        )

    @staticmethod
    def _validate(content: str, brief: ProjectBrief) -> NarrativeResult:
        try:
            # MiniMax OpenAI-compatible responses can prefix the answer with a
            # reasoning block. It is not part of the requested JSON artifact.
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.IGNORECASE)
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                payload = repair_json(content, return_objects=True)
            payload = NarrativeGenerator._normalise_response_envelope(payload)
            story = StoryPackage.model_validate(
                NarrativeGenerator._normalise_story(
                    payload["story"], brief, payload["screenplay"]
                )
            )
            return NarrativeResult(
                story=story,
                screenplay=ScreenplayPackage.model_validate(
                    NarrativeGenerator._normalise_screenplay(
                        payload["screenplay"], story
                    )
                ),
            )
        except (KeyError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            raise TextGenerationError(
                "text model output did not meet StoryMotion's story/screenplay contract: "
                f"{exc}"
            ) from exc

    @staticmethod
    def _normalise_response_envelope(payload: Any) -> dict[str, Any]:
        """Accept one unambiguous JSON candidate and reject lossy guesses."""
        if isinstance(payload, list):
            if len(payload) != 1 or not isinstance(payload[0], dict):
                raise TypeError(
                    "root JSON array must contain exactly one candidate object"
                )
            payload = payload[0]

        if not isinstance(payload, dict):
            raise TypeError(
                "root JSON value must be an object containing story and screenplay; "
                f"got {type(payload).__name__}"
            )

        required = {"story", "screenplay"}
        if required.issubset(payload):
            return payload

        candidates = [
            payload[key]
            for key in ("result", "data", "output")
            if isinstance(payload.get(key), dict)
            and required.issubset(payload[key])
        ]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            raise TypeError(
                "response envelope contains multiple story/screenplay candidates"
            )

        missing = ", ".join(sorted(required.difference(payload)))
        raise TypeError(
            "root JSON object must contain story and screenplay"
            + (f"; missing: {missing}" if missing else "")
        )

    @staticmethod
    def _normalise_story(
        raw: Any, brief: ProjectBrief, screenplay_raw: Any | None = None
    ) -> dict[str, Any]:
        """Keep creative content while making StoryPackage invariants deterministic."""
        if not isinstance(raw, dict):
            return raw
        worldview_raw = raw.get("worldview", {})
        worldview_raw = worldview_raw if isinstance(worldview_raw, dict) else {}
        locations_raw = worldview_raw.get("locations", [])
        locations = []
        if isinstance(locations_raw, list):
            for index, location in enumerate(locations_raw[: brief.max_locations], start=1):
                if isinstance(location, dict):
                    locations.append(
                        {
                            "id": location.get("id") or f"loc_{index:03d}",
                            "name": location.get("name") or f"场景{index}",
                            "visual_description": location.get("visual_description") or "具有电影感的叙事场景",
                        }
                    )
        if not locations:
            locations = [{"id": "loc_001", "name": "故事发生地", "visual_description": "与核心冲突相关的电影感场景"}]

        characters_raw = raw.get("characters", [])
        characters = []
        if isinstance(characters_raw, list):
            for index, character in enumerate(characters_raw[: brief.max_characters], start=1):
                if not isinstance(character, dict):
                    continue
                appearance = character.get("appearance", {})
                appearance = appearance if isinstance(appearance, dict) else {}
                personality = character.get("personality", ["坚定"])
                if not isinstance(personality, list) or not personality:
                    personality = [str(personality) or "坚定"]
                characters.append(
                    {
                        "id": character.get("id") or f"char_{index:03d}",
                        "name": character.get("name") or (brief.protagonist_name if index == 1 else f"角色{index}"),
                        "role": character.get("role") or ("protagonist" if index == 1 else "supporting"),
                        "age": character.get("age") if isinstance(character.get("age"), int) else None,
                        "personality": [str(item) for item in personality[:8] if str(item)] or ["坚定"],
                        "goal": character.get("goal") or brief.core_idea,
                        "ability": character.get("ability") if isinstance(character.get("ability"), str) else None,
                        "appearance": {
                            "hair": appearance.get("hair") or "黑发",
                            "clothing": appearance.get("clothing") or "符合题材的服装",
                            "distinctive_features": appearance.get("distinctive_features", []) if isinstance(appearance.get("distinctive_features", []), list) else [],
                        },
                        "visual_prompt_zh": character.get("visual_prompt_zh") or "中国动画风格角色设定",
                        "visual_prompt_en": character.get("visual_prompt_en") or "cinematic anime character design",
                    }
                )
        if not characters:
            characters = [{"id": "char_001", "name": brief.protagonist_name, "role": "protagonist", "age": None, "personality": ["坚定"], "goal": brief.core_idea, "ability": None, "appearance": {"hair": "黑发", "clothing": "符合题材的服装", "distinctive_features": []}, "visual_prompt_zh": "中国动画风格主角设定", "visual_prompt_en": "cinematic anime protagonist design"}]
        if brief.protagonist_name not in {item["name"] for item in characters}:
            characters[0]["name"] = brief.protagonist_name
            characters[0]["role"] = "protagonist"

        source_text = json.dumps(
            {
                "story_text": raw.get("story_text", ""),
                "screenplay": screenplay_raw,
            },
            ensure_ascii=False,
        )
        props = NarrativeGenerator._normalise_props(raw.get("props", []), source_text)

        rule = worldview_raw.get("special_rule") or brief.core_idea
        if isinstance(rule, list):
            rule = "；".join(str(item) for item in rule if str(item))
        beats_raw = raw.get("beats", [])
        valid_beats = (
            isinstance(beats_raw, list)
            and [item.get("beat_type") for item in beats_raw if isinstance(item, dict)]
            == ["hook", "setup", "conflict", "reversal", "cliffhanger"]
            and sum(item.get("duration", 0) for item in beats_raw if isinstance(item, dict)) == brief.target_duration
        )
        if valid_beats:
            beats = beats_raw
        else:
            base, remainder = divmod(brief.target_duration, 5)
            durations = [base + int(index < remainder) for index in range(5)]
            contents = ["危机突然出现", "主角发现规则", "主角直面冲突", "局势发生反转", "留下下一集悬念"]
            beats = [
                {"beat_type": kind, "duration": duration, "content": content}
                for kind, duration, content in zip(
                    ("hook", "setup", "conflict", "reversal", "cliffhanger"), durations, contents
                )
            ]
        return {
            "title": raw.get("title") or f"{brief.protagonist_name}的抉择",
            "logline": raw.get("logline") or brief.core_idea,
            "target_duration": brief.target_duration,
            "worldview": {
                "world_name": worldview_raw.get("world_name") or "故事世界",
                "era": worldview_raw.get("era") or "当代",
                "power_system": worldview_raw.get("power_system") or "核心规则驱动",
                "special_rule": rule if isinstance(rule, str) else brief.core_idea,
                "locations": locations,
            },
            "characters": characters,
            "props": props,
            "beats": beats,
            "story_text": raw.get("story_text") or f"{brief.protagonist_name}卷入了{brief.core_idea}。面对不断升级的代价，{brief.protagonist_name}必须作出选择，而真相才刚刚浮现。",
        }

    @staticmethod
    def _normalise_props(raw: Any, source_text: str) -> list[dict[str, Any]]:
        props: list[dict[str, Any]] = []
        if isinstance(raw, list):
            for value in raw[:8]:
                if not isinstance(value, dict):
                    continue
                name = str(value.get("name") or "").strip()
                if not name:
                    continue
                aliases = value.get("aliases", [])
                features = value.get("continuity_features", [])
                props.append(
                    {
                        "id": (
                            value.get("id")
                            if isinstance(value.get("id"), str)
                            and re.fullmatch(r"prop_[A-Za-z0-9_-]+", value["id"])
                            else f"prop_{len(props) + 1:03d}"
                        ),
                        "name": name,
                        "visual_description": (
                            value.get("visual_description")
                            if isinstance(value.get("visual_description"), str)
                            and value["visual_description"].strip()
                            else f"{name}的固定动画道具设计"
                        ),
                        "continuity_features": (
                            [str(item) for item in features[:8] if str(item)]
                            if isinstance(features, list)
                            else []
                        ),
                        "aliases": (
                            [str(item) for item in aliases[:8] if str(item)]
                            if isinstance(aliases, list)
                            else []
                        ),
                    }
                )

        known_terms = {
            term
            for prop in props
            for term in (prop["name"], *prop["aliases"])
        }
        for name, aliases, description, features in COMMON_PROP_CATALOG:
            if len(props) >= 8:
                break
            if not any(alias in source_text for alias in aliases):
                continue
            if any(alias in known_terms for alias in aliases):
                continue
            props.append(
                {
                    "id": f"prop_{len(props) + 1:03d}",
                    "name": name,
                    "visual_description": description,
                    "continuity_features": list(features),
                    "aliases": list(aliases),
                }
            )
            known_terms.update(aliases)
        return props

    @staticmethod
    def _normalise_screenplay(raw: Any, story: StoryPackage) -> dict[str, Any]:
        """Derive deterministic screenplay fields from the validated story."""
        if not isinstance(raw, dict):
            return raw
        character_ids = {character.id for character in story.characters}
        location_ids = {location.id for location in story.worldview.locations}
        props = {prop.id: prop for prop in story.props}
        raw_scenes = raw.get("scenes", [])
        scenes: list[dict[str, Any]] = []
        if isinstance(raw_scenes, list):
            for index, value in enumerate(raw_scenes, start=1):
                if not isinstance(value, dict):
                    continue
                characters = (
                    [item for item in value.get("characters", []) if item in character_ids]
                    if isinstance(value.get("characters", []), list)
                    else []
                )
                dialogues = []
                for dialogue in value.get("dialogues", []):
                    if not isinstance(dialogue, dict):
                        continue
                    speaker = dialogue.get("speaker_id", dialogue.get("character_id"))
                    text = dialogue.get("text")
                    if speaker in character_ids and isinstance(text, str) and text.strip():
                        if speaker not in characters:
                            characters.append(speaker)
                        dialogues.append(
                            {"speaker_id": speaker, "text": text, "emotion": dialogue.get("emotion")}
                        )
                location = value.get("location_id")
                scene_text = json.dumps(value, ensure_ascii=False)
                requested_props = value.get("prop_ids", value.get("props", []))
                scene_prop_ids: list[str] = []
                if isinstance(requested_props, list):
                    for requested in requested_props:
                        requested_value = (
                            requested.get("id") or requested.get("name")
                            if isinstance(requested, dict)
                            else requested
                        )
                        for prop in props.values():
                            if requested_value in (prop.id, prop.name, *prop.aliases):
                                if prop.id not in scene_prop_ids:
                                    scene_prop_ids.append(prop.id)
                for prop in props.values():
                    terms = (prop.name, *prop.aliases)
                    if any(term and term in scene_text for term in terms):
                        if prop.id not in scene_prop_ids:
                            scene_prop_ids.append(prop.id)
                scenes.append(
                    {
                        "scene_id": value.get("scene_id") or f"scene_{index:03d}",
                        "location_id": location if location in location_ids else story.worldview.locations[0].id,
                        "duration": value.get("duration", 0),
                        "characters": characters,
                        "prop_ids": scene_prop_ids,
                        "scene_goal": value.get("scene_goal") or value.get("action") or "推进剧情",
                        "action": value.get("action") or value.get("visual_prompt") or "角色做出关键选择。",
                        "dialogues": dialogues,
                        "voiceover": value.get("voiceover"),
                        "emotion": value.get("emotion") or "紧张",
                        "transition": value.get("transition"),
                    }
                )
        if scenes:
            durations = [
                int(scene["duration"])
                if isinstance(scene["duration"], (int, float)) and scene["duration"] > 0
                else 0
                for scene in scenes
            ]
            if sum(durations) != story.target_duration:
                base, remainder = divmod(story.target_duration, len(scenes))
                durations = [base + int(index < remainder) for index in range(len(scenes))]
            for scene, duration in zip(scenes, durations):
                scene["duration"] = duration
        return {
            "title": story.title,
            "target_duration": story.target_duration,
            "characters": [item.model_dump(mode="json") for item in story.characters],
            "locations": [item.model_dump(mode="json") for item in story.worldview.locations],
            "props": [item.model_dump(mode="json") for item in story.props],
            "scenes": scenes,
        }
