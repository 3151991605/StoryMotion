"""Run a bounded four-node MiniMax-M3 story generation graph once."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from storymotion.models import (
    CharacterPackage,
    PlotPlan,
    ProjectBrief,
    StoryDraft,
    StoryPackage,
    Worldview,
)
from storymotion.services import assemble_story_package
from verify_minimax_access import ENV_FILE, load_local_env
from verify_minimax_structured_output import extract_json_object, post_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BRIEF_FILE = (
    ROOT / "outputs" / "verification" / "minimax_m3_project_brief_run_01.json"
)
OUTPUT_DIR = ROOT / "outputs" / "verification" / "story_graph"
SUMMARY_FILE = ROOT / "outputs" / "verification" / "minimax_m3_story_graph_summary.json"
FINAL_FILE = OUTPUT_DIR / "story_package.json"

NODE_ORDER = ("worldview", "characters", "plot", "writer")

SYSTEM_PROMPTS = {
    "worldview": """你是 StoryMotion 的世界观 Agent。只输出一个合法 JSON 对象，不输出 Markdown、解释或思考过程。
顶层严格包含且只包含 world_name, era, power_system, special_rule, locations。
locations 必须恰好 1 个元素，字段严格为 id, name, visual_description，id 必须是 loc_001。
世界观只服务当前 60 秒剧情，所有字符串简洁具体。""",
    "characters": """你是 StoryMotion 的角色 Agent。只输出一个合法 JSON 对象，不输出 Markdown、解释或思考过程。
顶层严格包含且只包含 characters，必须恰好 2 个角色。
主角 id 必须是 char_001，姓名必须与 ProjectBrief 一致；另一角色 id 必须是 char_002。
每个角色严格包含 id, name, role, age, personality, goal, ability, appearance, visual_prompt_zh, visual_prompt_en。
age 必须是整数或 null，禁止用描述文本表示年龄。
personality 必须是 JSON 字符串数组，例如 ["冷静", "执着"]。
appearance 严格包含 hair, clothing, distinctive_features；distinctive_features 必须是 JSON 字符串数组。
视觉提示简洁，外观固定，不增加第三个角色。""",
    "plot": """你是 StoryMotion 的剧情规划 Agent。只输出一个合法 JSON 对象，不输出 Markdown、解释或思考过程。
顶层严格包含且只包含 target_duration, beats。target_duration 必须是整数 60。
beats 恰好 5 段，每段严格包含 beat_type, duration, content，顺序和时长必须是：
hook=10, setup=10, conflict=20, reversal=10, cliffhanger=10。
只使用输入中的两个角色和一个地点，每段 content 简洁可视化。""",
    "writer": """你是 StoryMotion 的短篇故事 Writer Agent。只输出一个合法 JSON 对象，不输出 Markdown、解释或思考过程。
顶层严格包含且只包含 title, logline, story_text。
story_text 必须为 500–650 个中文字符，只使用输入中的两个角色和一个地点，严格遵循五段剧情节拍。
重点写可视化动作、环境变化和少量对白，避免抽象心理描写，不添加新角色、地点、能力或支线。""",
}

MODEL_TYPES: dict[str, type[BaseModel]] = {
    "worldview": Worldview,
    "characters": CharacterPackage,
    "plot": PlotPlan,
    "writer": StoryDraft,
}


def compact_json(value: BaseModel) -> str:
    return json.dumps(value.model_dump(), ensure_ascii=False, separators=(",", ":"))


def build_user_prompt(
    node: str, brief: ProjectBrief, state: dict[str, BaseModel]
) -> str:
    context: dict[str, Any] = {"brief": brief.model_dump()}
    for dependency in NODE_ORDER:
        if dependency == node:
            break
        if dependency in state:
            context[dependency] = state[dependency].model_dump()
    return "根据以下已验证状态完成你的唯一任务：" + json.dumps(
        context, ensure_ascii=False, separators=(",", ":")
    )


def build_payload(
    node: str, brief: ProjectBrief, state: dict[str, BaseModel]
) -> dict[str, Any]:
    return {
        "model": "MiniMax-M3",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPTS[node]},
            {"role": "user", "content": build_user_prompt(node, brief, state)},
        ],
        "stream": False,
        "temperature": 0.2,
        "max_completion_tokens": 2048,
    }


def validate_node_specific(
    node: str, value: BaseModel, brief: ProjectBrief
) -> None:
    if node == "worldview":
        worldview = value
        if not isinstance(worldview, Worldview) or len(worldview.locations) != 1:
            raise ValueError("worldview node requires exactly 1 location")
    elif node == "characters":
        package = value
        if not isinstance(package, CharacterPackage) or len(package.characters) != 2:
            raise ValueError("character node requires exactly 2 characters")
        if brief.protagonist_name not in {
            character.name for character in package.characters
        }:
            raise ValueError("character node omitted the ProjectBrief protagonist")
    elif node == "plot":
        plan = value
        if not isinstance(plan, PlotPlan) or plan.target_duration != brief.target_duration:
            raise ValueError("plot target_duration does not match ProjectBrief")
    elif node == "writer":
        draft = value
        if not isinstance(draft, StoryDraft) or len(draft.story_text) > 650:
            raise ValueError("writer story_text must contain 500–650 characters")


def aggregate_usage(results: list[dict[str, Any]]) -> dict[str, int]:
    fields = ("prompt_tokens", "completion_tokens", "total_tokens")
    return {
        field: sum(
            int(result.get("usage", {}).get(field, 0) or 0) for result in results
        )
        for field in fields
    }


def load_cached_state(
    brief: ProjectBrief, output_dir: Path
) -> tuple[dict[str, BaseModel], list[dict[str, Any]]]:
    state: dict[str, BaseModel] = {}
    results: list[dict[str, Any]] = []
    for node in NODE_ORDER:
        output_file = output_dir / f"{node}.json"
        if not output_file.exists():
            break
        try:
            parsed = MODEL_TYPES[node].model_validate_json(
                output_file.read_text(encoding="utf-8")
            )
            validate_node_specific(node, parsed, brief)
        except (OSError, ValueError, ValidationError):
            break
        state[node] = parsed
        results.append(
            {
                "node": node,
                "passed": True,
                "cached": True,
                "output_file": str(output_file),
                "latency_seconds": 0.0,
            }
        )
    return state, results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brief", type=Path, default=DEFAULT_BRIEF_FILE)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse contiguous validated node outputs from the output directory.",
    )
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

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    api_base = os.getenv("MINIMAX_API_BASE", "https://api.minimaxi.com").rstrip("/")
    url = f"{api_base}/v1/chat/completions"
    state: dict[str, BaseModel] = {}
    results: list[dict[str, Any]] = []
    if args.resume:
        state, results = load_cached_state(brief, OUTPUT_DIR)
        for cached_node in state:
            print(f"{cached_node.upper()}_CACHED")

    for node in NODE_ORDER[len(state) :]:
        started = time.perf_counter()
        result: dict[str, Any] = {
            "node": node,
            "passed": False,
            "cached": False,
        }
        content = ""
        try:
            response = post_json(
                url,
                api_key,
                build_payload(node, brief, state),
                timeout_seconds=args.timeout,
            )
            content = response["choices"][0]["message"]["content"]
            finish_reason = response["choices"][0].get("finish_reason")
            result.update(
                {
                    "response_model": response.get("model"),
                    "finish_reason": finish_reason,
                    "usage": response.get("usage", {}),
                }
            )
            if finish_reason == "length":
                raise ValueError("response was truncated because finish_reason=length")
            parsed = MODEL_TYPES[node].model_validate(extract_json_object(content))
            validate_node_specific(node, parsed, brief)
            state[node] = parsed
            output_file = OUTPUT_DIR / f"{node}.json"
            output_file.write_text(
                json.dumps(parsed.model_dump(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            result.update(
                {"passed": True, "output_file": str(output_file.relative_to(ROOT))}
            )
        except (KeyError, IndexError, TypeError, ValueError, RuntimeError, ValidationError) as exc:
            result["error"] = str(exc)
            if content:
                raw_file = OUTPUT_DIR / f"{node}_failure.txt"
                raw_file.write_text(content, encoding="utf-8")
                result["raw_failure_file"] = str(raw_file.relative_to(ROOT))
        result["latency_seconds"] = round(time.perf_counter() - started, 3)
        results.append(result)
        print(
            f"{node.upper()}_{'PASS' if result['passed'] else 'FAIL'} "
            f"latency={result['latency_seconds']}s"
        )
        if not result["passed"]:
            print(result.get("error", "unknown error"), file=sys.stderr)
            break

    final_story: StoryPackage | None = None
    assembly_error: str | None = None
    if len(state) == len(NODE_ORDER):
        try:
            final_story = assemble_story_package(
                brief=brief,
                worldview=state["worldview"],
                characters=state["characters"],
                plot=state["plot"],
                draft=state["writer"],
            )
            FINAL_FILE.write_text(
                json.dumps(final_story.model_dump(), ensure_ascii=False, indent=2)
                + "\n",
                encoding="utf-8",
            )
        except (TypeError, ValueError, ValidationError) as exc:
            assembly_error = str(exc)

    summary = {
        "requested_model": "MiniMax-M3",
        "input_brief": str(args.brief),
        "timeout_seconds_per_node": args.timeout,
        "max_requests": len(NODE_ORDER),
        "requests_made": sum(not result.get("cached", False) for result in results),
        "cached_nodes": [
            result["node"] for result in results if result.get("cached", False)
        ],
        "completed_nodes": list(state),
        "last_completed_node": list(state)[-1] if state else None,
        "passed": final_story is not None,
        "assembly_error": assembly_error,
        "usage": aggregate_usage(results),
        "results": results,
    }
    if final_story is not None:
        summary.update(
            {
                "story_text_characters": len(final_story.story_text),
                "character_count": len(final_story.characters),
                "location_count": len(final_story.worldview.locations),
                "beat_count": len(final_story.beats),
                "output_file": str(FINAL_FILE.relative_to(ROOT)),
            }
        )
    SUMMARY_FILE.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved: {SUMMARY_FILE}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
