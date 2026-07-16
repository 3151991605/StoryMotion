from __future__ import annotations

import json
from pathlib import Path

from storymotion.models import StoryMotionBundle

from scripts.run_end_to_end_demo import (
    DEFAULT_BRIEF_FILE,
    DEFAULT_SCREENPLAY_FILE,
    DEFAULT_STORY_FILE,
    find_workspace_tool,
    load_inputs,
)


FIXTURE_FILE = (
    Path(__file__).resolve().parent / "fixtures" / "valid_storymotion_bundle.json"
)


def test_loads_three_protocol_inputs(tmp_path: Path) -> None:
    fixture = StoryMotionBundle.model_validate_json(
        FIXTURE_FILE.read_text(encoding="utf-8")
    )
    paths = []
    for name, value in (
        ("brief.json", fixture.brief),
        ("story.json", fixture.story),
        ("screenplay.json", fixture.screenplay),
    ):
        path = tmp_path / name
        path.write_text(
            json.dumps(value.model_dump(mode="json"), ensure_ascii=False),
            encoding="utf-8",
        )
        paths.append(path)

    brief, story, screenplay = load_inputs(
        brief_file=paths[0],
        story_file=paths[1],
        screenplay_file=paths[2],
    )

    assert brief == fixture.brief
    assert story == fixture.story
    assert screenplay == fixture.screenplay


def test_finds_workspace_local_tool(tmp_path: Path) -> None:
    tool = tmp_path / ".tools" / "ffmpeg" / "runtime" / "bin" / "ffmpeg.exe"
    tool.parent.mkdir(parents=True)
    tool.touch()

    assert find_workspace_tool(tmp_path, "ffmpeg") == tool


def test_default_verification_inputs_use_canonical_protocols() -> None:
    brief, story, screenplay = load_inputs(
        brief_file=DEFAULT_BRIEF_FILE,
        story_file=DEFAULT_STORY_FILE,
        screenplay_file=DEFAULT_SCREENPLAY_FILE,
    )

    assert brief.target_duration == story.target_duration
    assert story.target_duration == screenplay.target_duration
