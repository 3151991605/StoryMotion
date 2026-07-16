"""Verify one cached StoryMotion Writer node through MiniMax's Anthropic API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from storymotion.models import (
    CharacterPackage,
    PlotPlan,
    ProjectBrief,
    StoryDraft,
    Worldview,
)
from storymotion.services import assemble_story_package
from verify_minimax_access import ENV_FILE, load_local_env
from verify_minimax_structured_output import extract_json_object


ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_DIR = ROOT / "outputs" / "verification"
GRAPH_DIR = VERIFICATION_DIR / "story_graph"
DEFAULT_BRIEF_FILE = VERIFICATION_DIR / "minimax_m3_project_brief_run_01.json"
FINAL_FILE = GRAPH_DIR / "story_package.json"
WRITER_FILE = GRAPH_DIR / "writer_anthropic_m27.json"
FAILURE_FILE = GRAPH_DIR / "writer_anthropic_m27_failure.txt"
SUMMARY_FILE = VERIFICATION_DIR / "minimax_m27_anthropic_writer_summary.json"

SYSTEM_PROMPT = """你是 StoryMotion 的短篇故事 Writer Agent。
只输出一个合法 JSON 对象，不要输出 Markdown、解释或思考过程。
顶层必须严格包含且只包含 title、logline、story_text。
story_text 必须为 500-650 个中文字符，严格遵循输入中的五段剧情节拍。
重点写可视化动作、环境变化和少量对白；不得增加角色、地点、能力或支线。"""


def build_writer_context(
    brief: ProjectBrief,
    worldview: Worldview,
    characters: CharacterPackage,
    plot: PlotPlan,
) -> dict[str, Any]:
    return {
        "brief": {
            "genre": brief.genre,
            "style": brief.style,
            "protagonist_name": brief.protagonist_name,
            "core_idea": brief.core_idea,
            "ending_type": brief.ending_type,
        },
        "world": {
            "world_name": worldview.world_name,
            "special_rule": worldview.special_rule,
            "locations": [
                {
                    "id": location.id,
                    "name": location.name,
                    "visual_description": location.visual_description,
                }
                for location in worldview.locations
            ],
        },
        "characters": [
            {
                "id": character.id,
                "name": character.name,
                "role": character.role,
                "goal": character.goal,
                "ability": character.ability,
            }
            for character in characters.characters
        ],
        "beats": [beat.model_dump() for beat in plot.beats],
    }


def build_payload(
    brief: ProjectBrief,
    worldview: Worldview,
    characters: CharacterPackage,
    plot: PlotPlan,
    *,
    model: str = "MiniMax-M2.7",
    max_tokens: int = 4096,
) -> dict[str, Any]:
    context = build_writer_context(brief, worldview, characters, plot)
    return {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0.2,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": json.dumps(
                    context, ensure_ascii=False, separators=(",", ":")
                ),
            }
        ],
    }


def post_anthropic_json(
    url: str,
    api_key: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    request = Request(
        url,
        method="POST",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "StoryMotion-Feasibility-Probe/0.3",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError(
            f"Network read timed out after {timeout_seconds} seconds"
        ) from exc
    try:
        value = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON API response: {body[:500]}") from exc
    if not isinstance(value, dict):
        raise RuntimeError("API response root is not an object")
    return value


def extract_text_blocks(response: dict[str, Any]) -> str:
    blocks = response.get("content")
    if not isinstance(blocks, list):
        raise ValueError("Anthropic response content is not a list")
    texts = [
        block["text"]
        for block in blocks
        if isinstance(block, dict)
        and block.get("type") == "text"
        and isinstance(block.get("text"), str)
    ]
    content = "".join(texts).strip()
    if not content:
        raise ValueError("Anthropic response did not contain a text block")
    return content


def validate_draft(value: dict[str, Any]) -> StoryDraft:
    draft = StoryDraft.model_validate(value)
    if len(draft.story_text) > 650:
        raise ValueError("writer story_text must contain 500-650 characters")
    return draft


def load_inputs(brief_file: Path) -> tuple[ProjectBrief, Worldview, CharacterPackage, PlotPlan]:
    return (
        ProjectBrief.model_validate_json(brief_file.read_text(encoding="utf-8")),
        Worldview.model_validate_json((GRAPH_DIR / "worldview.json").read_text(encoding="utf-8")),
        CharacterPackage.model_validate_json((GRAPH_DIR / "characters.json").read_text(encoding="utf-8")),
        PlotPlan.model_validate_json((GRAPH_DIR / "plot.json").read_text(encoding="utf-8")),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", type=Path, default=DEFAULT_BRIEF_FILE)
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
        brief, worldview, characters, plot = load_inputs(args.brief)
    except (OSError, ValidationError) as exc:
        print(f"Invalid cached input: {exc}", file=sys.stderr)
        return 2

    GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    base_url = os.getenv(
        "MINIMAX_ANTHROPIC_BASE", "https://api.minimaxi.com/anthropic"
    ).rstrip("/")
    url = f"{base_url}/v1/messages"
    payload = build_payload(
        brief,
        worldview,
        characters,
        plot,
        model=args.model,
        max_tokens=args.max_tokens,
    )
    started = time.perf_counter()
    summary: dict[str, Any] = {
        "requested_model": args.model,
        "endpoint_format": "anthropic",
        "max_tokens": args.max_tokens,
        "requests_made": 1,
        "cached_nodes": ["worldview", "characters", "plot"],
        "passed": False,
    }
    content = ""
    try:
        response = post_anthropic_json(
            url, api_key, payload, timeout_seconds=args.timeout
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
        draft = validate_draft(extract_json_object(content))
        story = assemble_story_package(
            brief=brief,
            worldview=worldview,
            characters=characters,
            plot=plot,
            draft=draft,
        )
        WRITER_FILE.write_text(
            json.dumps(draft.model_dump(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        FINAL_FILE.write_text(
            json.dumps(story.model_dump(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summary.update(
            {
                "passed": True,
                "story_text_characters": len(draft.story_text),
                "writer_output_file": str(WRITER_FILE.relative_to(ROOT)),
                "story_package_file": str(FINAL_FILE.relative_to(ROOT)),
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
