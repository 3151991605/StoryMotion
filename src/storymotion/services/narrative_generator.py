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
硬性规则：story.beats 的顺序固定为 hook、setup、conflict、reversal、cliffhanger，时长和 target_duration 精确相等；主角姓名必须出现。每个 scene 使用 scene_id、location_id、duration、characters、scene_goal、action、dialogues、voiceover、emotion、transition。文本使用中文。"""


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
            "screenplay 示例结构：{\"scenes\":[{\"scene_id\":\"scene_001\",\"location_id\":\"loc_001\",\"duration\":15,\"characters\":[\"char_001\"],\"scene_goal\":\"...\",\"action\":\"...\",\"dialogues\":[],\"voiceover\":null,\"emotion\":\"紧张\",\"transition\":null}]}"
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
                    "不要 Markdown 或解释。逐项修复所有时长、ID、跨层引用和 JSON 语法问题。\n"
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
            story = StoryPackage.model_validate(
                NarrativeGenerator._normalise_story(payload["story"], brief)
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
    def _normalise_story(raw: Any, brief: ProjectBrief) -> dict[str, Any]:
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
            "beats": beats,
            "story_text": raw.get("story_text") or f"{brief.protagonist_name}卷入了{brief.core_idea}。面对不断升级的代价，{brief.protagonist_name}必须作出选择，而真相才刚刚浮现。",
        }

    @staticmethod
    def _normalise_screenplay(raw: Any, story: StoryPackage) -> dict[str, Any]:
        """Derive deterministic screenplay fields from the validated story."""
        if not isinstance(raw, dict):
            return raw
        character_ids = {character.id for character in story.characters}
        location_ids = {location.id for location in story.worldview.locations}
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
                scenes.append(
                    {
                        "scene_id": value.get("scene_id") or f"scene_{index:03d}",
                        "location_id": location if location in location_ids else story.worldview.locations[0].id,
                        "duration": value.get("duration", 0),
                        "characters": characters,
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
            "scenes": scenes,
        }
