from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from storymotion.models import (
    CharacterPackage,
    PlotPlan,
    StoryDraft,
    StoryMotionBundle,
)
from storymotion.services.story_assembler import assemble_story_package


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "valid_storymotion_bundle.json"


@pytest.fixture
def bundle() -> StoryMotionBundle:
    return StoryMotionBundle.model_validate_json(
        FIXTURE_PATH.read_text(encoding="utf-8")
    )


@pytest.fixture
def draft() -> StoryDraft:
    return StoryDraft(
        title="倒退十秒",
        logline="林辰在死亡瞬间觉醒回溯能力，并得知兄长可能尚在人世。",
        story_text=("林辰在废弃试炼塔中迎战玄兽，时间在死亡瞬间倒退十秒。" * 20)[:520],
    )


def test_assembles_story_package(
    bundle: StoryMotionBundle, draft: StoryDraft
) -> None:
    story = assemble_story_package(
        brief=bundle.brief,
        worldview=bundle.story.worldview,
        characters=CharacterPackage(characters=bundle.story.characters),
        plot=PlotPlan(
            target_duration=bundle.story.target_duration,
            beats=bundle.story.beats,
        ),
        draft=draft,
    )
    assert story.target_duration == 60
    assert story.story_text == draft.story_text
    assert story.total_beat_duration == 60


def test_assembler_rejects_missing_protagonist(
    bundle: StoryMotionBundle, draft: StoryDraft
) -> None:
    brief = bundle.brief.model_copy(update={"protagonist_name": "不存在的主角"})
    with pytest.raises(ValueError, match="protagonist"):
        assemble_story_package(
            brief=brief,
            worldview=bundle.story.worldview,
            characters=CharacterPackage(characters=bundle.story.characters),
            plot=PlotPlan(target_duration=60, beats=bundle.story.beats),
            draft=draft,
        )


def test_character_package_rejects_duplicate_ids(bundle: StoryMotionBundle) -> None:
    duplicate = [bundle.story.characters[0], bundle.story.characters[0]]
    with pytest.raises(ValidationError, match="duplicate character IDs"):
        CharacterPackage(characters=duplicate)


def test_story_draft_enforces_length() -> None:
    with pytest.raises(ValidationError, match="at least 500 characters"):
        StoryDraft(title="短", logline="过短", story_text="不足五百字")

