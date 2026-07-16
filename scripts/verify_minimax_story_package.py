"""Verify one MiniMax-M3 ProjectBrief-to-StoryPackage generation."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from storymotion.models import ProjectBrief, StoryPackage
from verify_minimax_access import ENV_FILE, load_local_env
from verify_minimax_structured_output import extract_json_object, post_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BRIEF_FILE = (
    ROOT / "outputs" / "verification" / "minimax_m3_project_brief_run_01.json"
)
OUTPUT_DIR = ROOT / "outputs" / "verification"
OUTPUT_FILE = OUTPUT_DIR / "minimax_m3_story_package.json"
SUMMARY_FILE = OUTPUT_DIR / "minimax_m3_story_package_summary.json"
RAW_FAILURE_FILE = OUTPUT_DIR / "minimax_m3_story_package_failure.txt"


SYSTEM_PROMPT = """你是 StoryMotion 的短漫剧故事生成 Agent。
只输出一个合法 JSON 对象，不输出 Markdown、解释、思考过程或额外文字。

顶层必须严格包含且只包含：
title, logline, target_duration, worldview, characters, beats, story_text。

紧凑输出要求：
1. target_duration 必须为整数 60。
2. worldview 必须包含 world_name, era, power_system, special_rule, locations。
3. locations 必须恰好 1 个地点，字段为 id, name, visual_description；id 必须为 loc_001。
4. characters 必须恰好 2 个角色。主角必须是 char_001，另一角色是 char_002。
5. 每个角色必须包含 id, name, role, age, personality, goal, ability, appearance,
   visual_prompt_zh, visual_prompt_en。appearance 必须包含 hair, clothing,
   distinctive_features。visual prompt 要简短。
6. beats 必须恰好 5 段，按以下顺序和时长输出：
   hook=10, setup=10, conflict=20, reversal=10, cliffhanger=10。
   每段字段必须为 beat_type, duration, content。
7. story_text 必须为 500–650 个中文字符，使用具体动作、画面和少量对白，
   避免抽象心理描写，不增加第三个角色或第二个地点。
8. 所有 JSON 键使用这里给出的英文名称，不得增加任何未知字段。"""


def validate_story_against_brief(
    story: StoryPackage, brief: ProjectBrief
) -> None:
    if story.target_duration != brief.target_duration:
        raise ValueError(
            "story target_duration does not match ProjectBrief: "
            f"{story.target_duration} != {brief.target_duration}"
        )
    if len(story.characters) > brief.max_characters:
        raise ValueError(
            f"character limit exceeded: {len(story.characters)} > "
            f"{brief.max_characters}"
        )
    if len(story.worldview.locations) > brief.max_locations:
        raise ValueError(
            f"location limit exceeded: {len(story.worldview.locations)} > "
            f"{brief.max_locations}"
        )
    if brief.protagonist_name not in {
        character.name for character in story.characters
    }:
        raise ValueError("ProjectBrief protagonist is missing from StoryPackage")


def validate_probe_requirements(story: StoryPackage) -> None:
    if len(story.characters) != 2:
        raise ValueError(f"probe requires exactly 2 characters; got {len(story.characters)}")
    if len(story.worldview.locations) != 1:
        raise ValueError(
            "probe requires exactly 1 location; "
            f"got {len(story.worldview.locations)}"
        )
    if not 500 <= len(story.story_text) <= 650:
        raise ValueError(
            "story_text must contain 500–650 characters; "
            f"got {len(story.story_text)}"
        )


def build_payload(brief: ProjectBrief) -> dict[str, Any]:
    brief_json = json.dumps(brief.model_dump(), ensure_ascii=False, separators=(",", ":"))
    return {
        "model": "MiniMax-M3",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"根据这个已经验证的 ProjectBrief 生成 StoryPackage：{brief_json}",
            },
        ],
        "stream": False,
        "temperature": 0.2,
        "max_completion_tokens": 2048,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", type=Path, default=DEFAULT_BRIEF_FILE)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    if not 30 <= args.timeout <= 300:
        parser.error("--timeout must be between 30 and 300 seconds")

    load_local_env(ENV_FILE)
    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if not api_key:
        print("Missing MINIMAX_API_KEY in .env", file=sys.stderr)
        return 2

    try:
        brief = ProjectBrief.model_validate_json(
            args.brief.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as exc:
        print(f"Invalid ProjectBrief input: {exc}", file=sys.stderr)
        return 2

    api_base = os.getenv("MINIMAX_API_BASE", "https://api.minimaxi.com").rstrip("/")
    payload = build_payload(brief)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    response: dict[str, Any] | None = None
    content = ""
    summary: dict[str, Any] = {
        "requested_model": payload["model"],
        "input_brief": str(args.brief),
        "timeout_seconds": args.timeout,
        "passed": False,
    }
    try:
        response = post_json(
            f"{api_base}/v1/chat/completions",
            api_key,
            payload,
            timeout_seconds=args.timeout,
        )
        content = response["choices"][0]["message"]["content"]
        finish_reason = response["choices"][0].get("finish_reason")
        if finish_reason == "length":
            raise ValueError("response was truncated because finish_reason=length")
        story = StoryPackage.model_validate(extract_json_object(content))
        validate_story_against_brief(story, brief)
        validate_probe_requirements(story)
        OUTPUT_FILE.write_text(
            json.dumps(story.model_dump(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summary.update(
            {
                "passed": True,
                "response_model": response.get("model"),
                "finish_reason": finish_reason,
                "usage": response.get("usage", {}),
                "character_count": len(story.characters),
                "location_count": len(story.worldview.locations),
                "beat_count": len(story.beats),
                "story_text_characters": len(story.story_text),
                "output_file": str(OUTPUT_FILE.relative_to(ROOT)),
            }
        )
    except (KeyError, IndexError, TypeError, ValueError, RuntimeError, ValidationError) as exc:
        summary["error"] = str(exc)
        if content:
            RAW_FAILURE_FILE.write_text(content, encoding="utf-8")
            summary["raw_failure_file"] = str(RAW_FAILURE_FILE.relative_to(ROOT))

    summary["latency_seconds"] = round(time.perf_counter() - started, 3)
    if response is not None:
        summary.setdefault("response_model", response.get("model"))
        summary.setdefault("usage", response.get("usage", {}))
        try:
            summary.setdefault(
                "finish_reason", response["choices"][0].get("finish_reason")
            )
        except (KeyError, IndexError, TypeError):
            pass

    SUMMARY_FILE.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved: {SUMMARY_FILE}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
