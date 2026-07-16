from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import verify_minimax_structured_output as probe  # noqa: E402


VALID_FLAT_BRIEF = {
    "genre": "东方玄幻",
    "style": ["热血", "悬疑"],
    "protagonist_name": "林辰",
    "core_idea": "主角每天可以让时间倒退十秒",
    "target_duration": 60,
    "max_characters": 3,
    "max_locations": 5,
    "ending_type": "cliffhanger",
}


def test_canonical_flat_brief_validates() -> None:
    brief = probe.validate_project_brief(VALID_FLAT_BRIEF)
    assert brief.max_characters == 3


def test_old_nested_constraints_shape_is_rejected() -> None:
    nested = dict(VALID_FLAT_BRIEF)
    nested["constraints"] = {
        "max_characters": nested.pop("max_characters"),
        "max_locations": nested.pop("max_locations"),
        "ending_type": nested.pop("ending_type"),
    }
    with pytest.raises(ValidationError):
        probe.validate_project_brief(nested)


def test_prompt_lists_canonical_flat_fields() -> None:
    for field_name in (
        "max_characters",
        "max_locations",
        "ending_type",
    ):
        assert field_name in probe.SYSTEM_PROMPT
    assert "constraints: 对象" not in probe.SYSTEM_PROMPT


def test_post_json_converts_socket_timeout_to_runtime_error(monkeypatch) -> None:
    def raise_timeout(*args, **kwargs):
        raise TimeoutError("read timed out")

    monkeypatch.setattr(probe, "urlopen", raise_timeout)
    with pytest.raises(RuntimeError, match="timed out"):
        probe.post_json("https://example.invalid", "test-key", {})
