"""Verify StoryPackage-to-ScreenplayPackage with one MiniMax request."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from storymotion.models import Scene, ScenePackage, StoryPackage
from storymotion.services import assemble_screenplay_package
from verify_minimax_access import ENV_FILE, load_local_env
from verify_minimax_anthropic_writer import extract_text_blocks, post_anthropic_json
from verify_minimax_structured_output import extract_json_object


ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_DIR = ROOT / "outputs" / "verification"
DEFAULT_STORY_FILE = VERIFICATION_DIR / "story_graph" / "story_package.json"
OUTPUT_DIR = VERIFICATION_DIR / "screenplay"
SCENE_FILE = OUTPUT_DIR / "scene_package.json"
SCREENPLAY_FILE = OUTPUT_DIR / "screenplay_package.json"
FAILURE_FILE = OUTPUT_DIR / "screenplay_failure.txt"
SUMMARY_FILE = VERIFICATION_DIR / "minimax_m27_screenplay_summary.json"
MAX_SPOKEN_CHARACTERS_PER_SECOND = 4.0

SYSTEM_PROMPT = """你是 StoryMotion 的漫剧改编导演 Agent。
只输出一个合法 JSON 对象，不要输出 Markdown、解释或思考过程。
顶层必须严格包含且只包含 target_duration、scenes，不要重复输出 title、characters、locations。
target_duration 必须为整数 60。scenes 必须恰好 5 个，按输入五段剧情节拍一一对应。
场景 ID 必须依次为 scene_001 至 scene_005；每段 duration 必须与对应剧情节拍时长相同。
每个场景严格包含 scene_id、location_id、duration、characters、scene_goal、action、dialogues、voiceover、emotion、transition。
characters 只能使用输入角色 ID；location_id 只能使用输入地点 ID。
dialogues 是数组，每项严格包含 speaker_id、text、emotion；speaker_id 必须同时出现在当前场景 characters 中。
每句对白不超过 60 个中文字符。每场所有对白与旁白的字符总数不得超过 duration×4：10 秒场景最多 40 字，20 秒场景最多 80 字。voiceover 和 transition 没有内容时必须为 null。
action 必须是镜头可直接表现的动作和环境变化，禁止抽象心理描写，禁止增加角色、地点、能力或支线。"""


def build_screenplay_context(story: StoryPackage) -> dict[str, Any]:
    return {
        "title": story.title,
        "logline": story.logline,
        "target_duration": story.target_duration,
        "characters": [
            {
                "id": character.id,
                "name": character.name,
                "role": character.role,
                "ability": character.ability,
                "appearance": {
                    "hair": character.appearance.hair,
                    "clothing": character.appearance.clothing,
                    "distinctive_features": character.appearance.distinctive_features,
                },
            }
            for character in story.characters
        ],
        "locations": [
            location.model_dump() for location in story.worldview.locations
        ],
        "beats": [beat.model_dump() for beat in story.beats],
        "story_text": story.story_text,
    }


def build_payload(
    story: StoryPackage,
    *,
    model: str = "MiniMax-M2.7",
    max_tokens: int = 4096,
) -> dict[str, Any]:
    return {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": json.dumps(
                    build_screenplay_context(story),
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            }
        ],
    }


def validate_for_story(package: ScenePackage, story: StoryPackage) -> None:
    if package.target_duration != story.target_duration:
        raise ValueError("scene target_duration does not match StoryPackage")
    if len(package.scenes) != 5:
        raise ValueError("screenplay probe requires exactly 5 scenes")

    expected_ids = [f"scene_{index:03d}" for index in range(1, 6)]
    actual_ids = [scene.scene_id for scene in package.scenes]
    if actual_ids != expected_ids:
        raise ValueError(f"scene IDs must be sequential: {expected_ids}")

    expected_durations = [beat.duration for beat in story.beats]
    actual_durations = [scene.duration for scene in package.scenes]
    if actual_durations != expected_durations:
        raise ValueError(
            "scene durations must match plot beat durations: "
            f"{actual_durations} != {expected_durations}"
        )

    character_ids = {character.id for character in story.characters}
    location_ids = {location.id for location in story.worldview.locations}
    for scene in package.scenes:
        if scene.location_id not in location_ids:
            raise ValueError(
                f"scene {scene.scene_id} references unknown location {scene.location_id}"
            )
        unknown_characters = set(scene.characters) - character_ids
        if unknown_characters:
            raise ValueError(
                f"scene {scene.scene_id} references unknown characters: "
                f"{sorted(unknown_characters)}"
            )
        for dialogue in scene.dialogues:
            if len(dialogue.text) > 60:
                raise ValueError(
                    f"dialogue in {scene.scene_id} exceeds 60 characters"
                )
        validate_spoken_pacing(scene)


def validate_spoken_pacing(scene: Scene) -> None:
    spoken_characters = sum(len(dialogue.text) for dialogue in scene.dialogues)
    if scene.voiceover:
        spoken_characters += len(scene.voiceover)
    limit = int(scene.duration * MAX_SPOKEN_CHARACTERS_PER_SECOND)
    if spoken_characters > limit:
        raise ValueError(
            f"spoken content in {scene.scene_id} exceeds pacing limit: "
            f"{spoken_characters} > {limit} characters for {scene.duration}s"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--story", type=Path, default=DEFAULT_STORY_FILE)
    parser.add_argument("--model", default="MiniMax-M2.7")
    parser.add_argument("--max-tokens", type=int, default=4096)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)
    if not 2048 <= args.max_tokens <= 16384:
        parser.error("--max-tokens must be between 2048 and 16384")
    if not 30 <= args.timeout <= 300:
        parser.error("--timeout must be between 30 and 300 seconds")

    load_local_env(ENV_FILE)
    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if not api_key:
        print("Missing MINIMAX_API_KEY in .env", file=sys.stderr)
        return 2
    try:
        story = StoryPackage.model_validate_json(args.story.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        print(f"Invalid StoryPackage input: {exc}", file=sys.stderr)
        return 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_url = os.getenv(
        "MINIMAX_ANTHROPIC_BASE", "https://api.minimaxi.com/anthropic"
    ).rstrip("/")
    payload = build_payload(
        story, model=args.model, max_tokens=args.max_tokens
    )
    summary: dict[str, Any] = {
        "requested_model": args.model,
        "endpoint_format": "anthropic",
        "max_tokens": args.max_tokens,
        "requests_made": 1,
        "input_story": str(args.story.relative_to(ROOT)),
        "passed": False,
    }
    content = ""
    started = time.perf_counter()
    try:
        response = post_anthropic_json(
            f"{base_url}/v1/messages",
            api_key,
            payload,
            timeout_seconds=args.timeout,
        )
        summary.update(
            {
                "response_model": response.get("model"),
                "stop_reason": response.get("stop_reason"),
                "usage": response.get("usage", {}),
                "base_resp": response.get("base_resp", {}),
            }
        )
        content = extract_text_blocks(response)
        if response.get("stop_reason") == "max_tokens":
            raise ValueError("response was truncated because stop_reason=max_tokens")
        scene_package = ScenePackage.model_validate(extract_json_object(content))
        validate_for_story(scene_package, story)
        screenplay = assemble_screenplay_package(
            story=story, scene_package=scene_package
        )
        SCENE_FILE.write_text(
            json.dumps(scene_package.model_dump(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        SCREENPLAY_FILE.write_text(
            json.dumps(screenplay.model_dump(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summary.update(
            {
                "passed": True,
                "scene_count": len(screenplay.scenes),
                "dialogue_count": sum(
                    len(scene.dialogues) for scene in screenplay.scenes
                ),
                "total_scene_duration": screenplay.total_scene_duration,
                "scene_package_file": str(SCENE_FILE.relative_to(ROOT)),
                "screenplay_package_file": str(SCREENPLAY_FILE.relative_to(ROOT)),
            }
        )
    except (KeyError, TypeError, ValueError, RuntimeError, ValidationError) as exc:
        summary["error"] = str(exc)
        if content:
            FAILURE_FILE.write_text(content, encoding="utf-8")
            summary["raw_failure_file"] = str(FAILURE_FILE.relative_to(ROOT))

    summary["latency_seconds"] = round(time.perf_counter() - started, 3)
    SUMMARY_FILE.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved: {SUMMARY_FILE}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
