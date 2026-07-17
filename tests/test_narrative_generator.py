from __future__ import annotations

import json
from pathlib import Path

import pytest

from storymotion.models import ProjectBrief
from storymotion.providers import TextGenerationError
from storymotion.services import CreationPipeline, NarrativeGenerator
from storymotion.providers import RuleShotProvider


class FakeClient:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)

    def complete(self, *, system: str, user: str) -> str:
        assert "只输出一个 JSON 对象" in system
        assert "target_duration" in user or "候选 JSON" in user
        return self.responses.pop(0)


def fixture_response() -> str:
    fixture = Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json"
    raw = json.loads(fixture.read_text(encoding="utf-8"))
    return json.dumps({"story": raw["story"], "screenplay": raw["screenplay"]}, ensure_ascii=False)


def test_creates_valid_bundle_and_rule_storyboard() -> None:
    raw = json.loads(fixture_response())
    brief = ProjectBrief.model_validate(json.loads((Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json").read_text(encoding="utf-8"))["brief"])
    bundle = CreationPipeline(NarrativeGenerator(FakeClient(json.dumps(raw))), RuleShotProvider()).create(brief)
    assert bundle.story.title == "倒退十秒"
    assert bundle.storyboard.total_shot_duration == 60


def test_rejects_non_json_model_reply() -> None:
    brief = ProjectBrief(genre="奇幻", style=["悬疑"], protagonist_name="林夏", core_idea="测试")
    with pytest.raises(TextGenerationError, match="contract"):
        NarrativeGenerator(
            FakeClient("not json", "still not json", "also not json")
        ).generate(brief)


def test_repairs_invalid_first_model_output() -> None:
    raw = json.loads(fixture_response())
    raw["screenplay"]["scenes"][0]["duration"] = 13
    invalid = json.dumps(raw, ensure_ascii=False)
    brief = ProjectBrief.model_validate(
        json.loads((Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json").read_text(encoding="utf-8"))["brief"]
    )
    result = NarrativeGenerator(FakeClient(invalid, fixture_response())).generate(brief)
    assert result.screenplay.total_scene_duration == brief.target_duration


def test_repairs_a_missing_json_comma_before_protocol_validation() -> None:
    valid = fixture_response()
    malformed = valid.replace(', "screenplay"', ' "screenplay"', 1)
    brief = ProjectBrief.model_validate(
        json.loads((Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json").read_text(encoding="utf-8"))["brief"]
    )
    result = NarrativeGenerator(FakeClient(malformed)).generate(brief)
    assert result.story.title == "倒退十秒"


def test_normalises_common_minimax_screenplay_aliases() -> None:
    raw = json.loads(fixture_response())
    scene = raw["screenplay"]["scenes"][0]
    scene["scene_number"] = 1
    scene.pop("scene_id")
    scene.pop("scene_goal")
    scene["visual_prompt"] = scene["action"]
    scene.pop("emotion")
    scene["duration"] = 13
    for field in ("title", "target_duration", "characters", "locations"):
        raw["screenplay"].pop(field)
    brief = ProjectBrief.model_validate(
        json.loads((Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json").read_text(encoding="utf-8"))["brief"]
    )
    result = NarrativeGenerator(FakeClient(json.dumps(raw, ensure_ascii=False))).generate(brief)
    assert result.screenplay.total_scene_duration == 60
    assert result.screenplay.scenes[0].scene_id == "scene_001"


def test_normalises_missing_story_beats_and_list_rule() -> None:
    raw = json.loads(fixture_response())
    raw["story"]["worldview"]["special_rule"] = ["规则一", "规则二"]
    raw["story"].pop("beats")
    raw["story"].pop("story_text")
    brief = ProjectBrief.model_validate(
        json.loads((Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json").read_text(encoding="utf-8"))["brief"]
    )
    result = NarrativeGenerator(FakeClient(json.dumps(raw, ensure_ascii=False))).generate(brief)
    assert result.story.total_beat_duration == brief.target_duration
    assert result.story.worldview.special_rule == "规则一；规则二"
