from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from storymotion.adapters import adapt_penshot_result, screenplay_to_penshot_text
from storymotion.models import ScreenplayPackage


FIXTURE_DIR = Path(__file__).parent / "fixtures"
SCREENPLAY_FILE = (
    Path(__file__).resolve().parents[1]
    / "outputs"
    / "verification"
    / "screenplay"
    / "screenplay_package_repaired.json"
)


@pytest.fixture
def screenplay() -> ScreenplayPackage:
    return ScreenplayPackage.model_validate_json(
        SCREENPLAY_FILE.read_text(encoding="utf-8")
    )


@pytest.fixture
def raw_result() -> dict:
    return json.loads(
        (FIXTURE_DIR / "penshot_fragments.json").read_text(encoding="utf-8")
    )


def test_adapts_documented_penshot_fragments(
    screenplay: ScreenplayPackage,
    raw_result: dict,
) -> None:
    package = adapt_penshot_result(raw_result, screenplay)

    assert package.title == screenplay.title
    assert package.target_duration == 60
    assert len(package.shots) == 6
    assert package.total_shot_duration == 60
    assert [shot.scene_id for shot in package.shots] == [
        "scene_001",
        "scene_002",
        "scene_003",
        "scene_003",
        "scene_004",
        "scene_005",
    ]
    assert package.shots[0].video_prompt == raw_result["fragments"][0]["prompt"]
    assert package.shots[0].image_prompt
    assert package.shots[0].audio_prompt


def test_adapter_rejects_fragment_that_crosses_scene_boundary(
    screenplay: ScreenplayPackage,
    raw_result: dict,
) -> None:
    invalid = deepcopy(raw_result)
    invalid["fragments"][0]["duration"] = 11.0
    invalid["fragments"][1]["duration"] = 9.0

    with pytest.raises(ValueError, match="crosses scene boundary"):
        adapt_penshot_result(invalid, screenplay)


def test_adapter_rejects_more_than_ten_fragments(
    screenplay: ScreenplayPackage,
    raw_result: dict,
) -> None:
    invalid = deepcopy(raw_result)
    invalid["fragments"] = invalid["fragments"] + deepcopy(
        invalid["fragments"][:5]
    )

    with pytest.raises(ValueError, match="5-10 fragments"):
        adapt_penshot_result(invalid, screenplay)


def test_serialized_chinese_screenplay_keeps_ids_and_dialogue(
    screenplay: ScreenplayPackage,
) -> None:
    text = screenplay_to_penshot_text(screenplay)

    assert "scene_001" in text
    assert "林辰" in text
    assert "顾倾" in text
    assert "时间主宰血脉" in text
    assert "总时长：60秒" in text
