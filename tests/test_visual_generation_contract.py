from __future__ import annotations

import pytest
from pydantic import ValidationError

from storymotion.models import KeyframeContract


def test_visual_generation_contract_requires_all_six_observable_fields() -> None:
    contract = KeyframeContract(
        character_appearances=["林辰：黑色短发，深灰宗门服"],
        start_keyframe="林辰站在破碎石柱前，左手握剑。",
        action="林辰挥剑格挡迎面而来的利爪。",
        result="利爪被剑锋弹开，林辰仍站在原位。",
        transition_from_previous="承接上一镜，林辰的剑已拔出并面向玄兽。",
        transition_to_next="下一镜从利爪弹开、林辰持剑站稳的状态继续。",
    )

    assert contract.character_appearances == ["林辰：黑色短发，深灰宗门服"]
    assert contract.result.startswith("利爪")


@pytest.mark.parametrize(
    "field",
    [
        "character_appearances",
        "start_keyframe",
        "action",
        "result",
        "transition_from_previous",
        "transition_to_next",
    ],
)
def test_visual_generation_contract_rejects_missing_required_field(field: str) -> None:
    data = {
        "character_appearances": ["林辰：黑色短发，深灰宗门服"],
        "start_keyframe": "林辰站在石柱前。",
        "action": "林辰挥剑格挡。",
        "result": "利爪被弹开。",
        "transition_from_previous": "承接上一镜的持剑姿势。",
        "transition_to_next": "下一镜从利爪弹开继续。",
    }
    data.pop(field)

    with pytest.raises(ValidationError):
        KeyframeContract.model_validate(data)


def test_visual_generation_contract_upgrades_v1_persisted_data() -> None:
    contract = KeyframeContract.model_validate(
        {
            "required_visuals": ["废弃试炼塔", "林辰：深灰宗门服"],
            "opening_state": "林辰面向玄兽。",
            "key_action": "林辰挥剑格挡。",
            "visible_result": "玄兽利爪被弹开。",
            "continuity_anchor": "服装、场景和月光保持一致。",
        }
    )

    assert contract.start_keyframe == "林辰面向玄兽。"
    assert contract.transition_from_previous == "服装、场景和月光保持一致。"
    assert contract.transition_to_next == "服装、场景和月光保持一致。"
