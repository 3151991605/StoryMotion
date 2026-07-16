from __future__ import annotations

import sys
import json
from pathlib import Path

from storymotion.models import StoryMotionBundle


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import verify_minimax_story_graph as probe  # noqa: E402


def test_graph_node_order_is_bounded_and_explicit() -> None:
    assert probe.NODE_ORDER == ("worldview", "characters", "plot", "writer")


def test_each_node_prompt_requires_json_only() -> None:
    assert set(probe.SYSTEM_PROMPTS) == set(probe.NODE_ORDER)
    for prompt in probe.SYSTEM_PROMPTS.values():
        assert "只输出一个合法 JSON 对象" in prompt


def test_character_prompt_makes_ambiguous_types_explicit() -> None:
    prompt = probe.SYSTEM_PROMPTS["characters"]
    assert "personality 必须是 JSON 字符串数组" in prompt
    assert "distinctive_features 必须是 JSON 字符串数组" in prompt
    assert "age 必须是整数或 null" in prompt


def test_resume_loads_only_contiguous_valid_cached_nodes(tmp_path: Path) -> None:
    fixture_path = (
        Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json"
    )
    bundle = StoryMotionBundle.model_validate_json(
        fixture_path.read_text(encoding="utf-8")
    )
    (tmp_path / "worldview.json").write_text(
        json.dumps(bundle.story.worldview.model_dump(), ensure_ascii=False),
        encoding="utf-8",
    )
    state, results = probe.load_cached_state(bundle.brief, tmp_path)
    assert list(state) == ["worldview"]
    assert results[0]["cached"] is True
