"""Repair one overlong screenplay voiceover with a bounded MiniMax request."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError

from storymotion.models import ScreenplayPackage
from storymotion.models.base import StrictModel
from verify_minimax_access import ENV_FILE, load_local_env
from verify_minimax_anthropic_writer import extract_text_blocks, post_anthropic_json
from verify_minimax_screenplay_adapter import validate_spoken_pacing
from verify_minimax_structured_output import extract_json_object


ROOT = Path(__file__).resolve().parents[1]
VERIFICATION_DIR = ROOT / "outputs" / "verification"
DEFAULT_SCREENPLAY_FILE = (
    VERIFICATION_DIR / "screenplay" / "screenplay_package_run_01.json"
)
OUTPUT_DIR = VERIFICATION_DIR / "screenplay"
OUTPUT_FILE = OUTPUT_DIR / "screenplay_package_repaired.json"
FAILURE_FILE = OUTPUT_DIR / "voiceover_repair_failure.txt"
SUMMARY_FILE = VERIFICATION_DIR / "minimax_m27_screenplay_repair_summary.json"

SYSTEM_PROMPT = """你是 StoryMotion 的口播节奏修复 Agent。
只输出一个合法 JSON 对象，不要输出 Markdown、解释或思考过程。
顶层必须严格包含且只包含 scene_id、voiceover。
scene_id 必须与输入一致。voiceover 必须是 1-40 个中文字符的精炼旁白。
旁白要补充画面含义，不要逐句重复 action，不得增加角色、地点、能力或事件。"""


class VoiceoverRepair(StrictModel):
    scene_id: str = Field(pattern=r"^scene_[A-Za-z0-9_-]+$")
    voiceover: str = Field(min_length=1, max_length=40)


def build_payload(
    screenplay: ScreenplayPackage,
    scene_id: str,
    *,
    model: str = "MiniMax-M2.7",
    max_tokens: int = 1024,
) -> dict[str, Any]:
    scene = next(
        (candidate for candidate in screenplay.scenes if candidate.scene_id == scene_id),
        None,
    )
    if scene is None:
        raise ValueError(f"unknown scene ID: {scene_id}")
    context = {
        "title": screenplay.title,
        "scene_id": scene.scene_id,
        "duration": scene.duration,
        "scene_goal": scene.scene_goal,
        "action": scene.action,
        "dialogues": [dialogue.model_dump() for dialogue in scene.dialogues],
        "current_voiceover": scene.voiceover,
        "maximum_total_spoken_characters": int(scene.duration * 4),
    }
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


def apply_voiceover_repair(
    screenplay: ScreenplayPackage,
    repair: VoiceoverRepair,
) -> ScreenplayPackage:
    data = screenplay.model_dump()
    matching = [
        scene for scene in data["scenes"] if scene["scene_id"] == repair.scene_id
    ]
    if len(matching) != 1:
        raise ValueError(f"repair target must match exactly one scene: {repair.scene_id}")
    matching[0]["voiceover"] = repair.voiceover
    repaired = ScreenplayPackage.model_validate(data)
    for scene in repaired.scenes:
        validate_spoken_pacing(scene)
    return repaired


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenplay", type=Path, default=DEFAULT_SCREENPLAY_FILE)
    parser.add_argument("--scene-id", default="scene_001")
    parser.add_argument("--model", default="MiniMax-M2.7")
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    if not 256 <= args.max_tokens <= 2048:
        parser.error("--max-tokens must be between 256 and 2048")
    if not 30 <= args.timeout <= 300:
        parser.error("--timeout must be between 30 and 300 seconds")

    load_local_env(ENV_FILE)
    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if not api_key:
        print("Missing MINIMAX_API_KEY in .env", file=sys.stderr)
        return 2
    try:
        screenplay = ScreenplayPackage.model_validate_json(
            args.screenplay.read_text(encoding="utf-8")
        )
        payload = build_payload(
            screenplay,
            args.scene_id,
            model=args.model,
            max_tokens=args.max_tokens,
        )
    except (OSError, ValueError, ValidationError) as exc:
        print(f"Invalid repair input: {exc}", file=sys.stderr)
        return 2

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_url = os.getenv(
        "MINIMAX_ANTHROPIC_BASE", "https://api.minimaxi.com/anthropic"
    ).rstrip("/")
    summary: dict[str, Any] = {
        "requested_model": args.model,
        "endpoint_format": "anthropic",
        "max_tokens": args.max_tokens,
        "requests_made": 1,
        "input_screenplay": str(args.screenplay.relative_to(ROOT)),
        "target_scene": args.scene_id,
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
        repair = VoiceoverRepair.model_validate(extract_json_object(content))
        if repair.scene_id != args.scene_id:
            raise ValueError(
                f"repair returned wrong scene ID: {repair.scene_id} != {args.scene_id}"
            )
        repaired = apply_voiceover_repair(screenplay, repair)
        OUTPUT_FILE.write_text(
            json.dumps(repaired.model_dump(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        target = next(
            scene for scene in repaired.scenes if scene.scene_id == args.scene_id
        )
        spoken_characters = len(target.voiceover or "") + sum(
            len(dialogue.text) for dialogue in target.dialogues
        )
        summary.update(
            {
                "passed": True,
                "repaired_voiceover": repair.voiceover,
                "repaired_voiceover_characters": len(repair.voiceover),
                "target_scene_spoken_characters": spoken_characters,
                "target_scene_spoken_limit": int(target.duration * 4),
                "screenplay_package_file": str(OUTPUT_FILE.relative_to(ROOT)),
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
