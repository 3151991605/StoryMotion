"""Measure MiniMax-M3 stability against the canonical ProjectBrief model."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import ValidationError

from storymotion.models import ProjectBrief
from verify_minimax_access import ENV_FILE, load_local_env


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "verification"
SUMMARY_FILE = OUTPUT_DIR / "minimax_m3_stability_summary.json"


SYSTEM_PROMPT = """你是 StoryMotion 的需求解析 Agent。
只输出一个合法 JSON 对象，不要输出 Markdown、解释、思考过程或额外文字。
JSON 必须严格包含且只包含以下 8 个顶层字段：
- genre: 非空字符串
- style: 非空字符串数组
- protagonist_name: 非空字符串
- core_idea: 非空字符串
- target_duration: 整数，值必须为 60
- max_characters: 整数，值必须为 3
- max_locations: 整数，值必须为 5
- ending_type: 字符串，值必须为 cliffhanger
不得创建 constraints 字段，不得把任何字段嵌套在其他对象中。"""

USER_PROMPT = """把下面的创意整理为结构化需求：
类型是东方玄幻，风格热血悬疑，主角叫林辰。
核心脑洞：主角每天可以让时间倒退十秒。
生成 60 秒竖屏漫剧，主要角色不超过 3 人，场景不超过 5 个，悬念结尾。"""


def post_json(
    url: str,
    api_key: str,
    payload: dict[str, Any],
    *,
    timeout_seconds: float = 60,
) -> Any:
    request = Request(
        url,
        method="POST",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "StoryMotion-Feasibility-Probe/0.2",
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
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON API response: {body[:500]}") from exc


def extract_json_object(content: str) -> dict[str, Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
    start = cleaned.find("{")
    if start < 0:
        raise ValueError("model response did not contain a JSON object")
    value, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    if not isinstance(value, dict):
        raise ValueError("model response JSON root is not an object")
    return value


def validate_project_brief(value: dict[str, Any]) -> ProjectBrief:
    return ProjectBrief.model_validate(value)


def build_payload() -> dict[str, Any]:
    return {
        "model": "MiniMax-M3",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT},
        ],
        "stream": False,
        "temperature": 0.2,
        "max_completion_tokens": 1200,
    }


def parse_run_count(value: str) -> int:
    try:
        count = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("runs must be an integer") from exc
    if not 1 <= count <= 3:
        raise argparse.ArgumentTypeError("runs must be between 1 and 3")
    return count


def sum_usage(results: list[dict[str, Any]]) -> dict[str, int]:
    fields = ("prompt_tokens", "completion_tokens", "total_tokens")
    return {
        field: sum(
            int(result.get("usage", {}).get(field, 0) or 0) for result in results
        )
        for field in fields
    }


def run_once(
    *, run_number: int, url: str, api_key: str, payload: dict[str, Any]
) -> dict[str, Any]:
    started = time.perf_counter()
    result: dict[str, Any] = {"run": run_number, "passed": False}
    try:
        response = post_json(url, api_key, payload)
        content = response["choices"][0]["message"]["content"]
        brief = validate_project_brief(extract_json_object(content))
        output_file = OUTPUT_DIR / f"minimax_m3_project_brief_run_{run_number:02d}.json"
        output_file.write_text(
            json.dumps(brief.model_dump(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result.update(
            {
                "passed": True,
                "response_model": response.get("model"),
                "usage": response.get("usage", {}),
                "output_file": str(output_file.relative_to(ROOT)),
            }
        )
    except (KeyError, IndexError, TypeError, ValueError, RuntimeError, ValidationError) as exc:
        result["error"] = str(exc)
    result["latency_seconds"] = round(time.perf_counter() - started, 3)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=parse_run_count, default=1)
    args = parser.parse_args(argv)

    load_local_env(ENV_FILE)
    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if not api_key:
        print("Missing MINIMAX_API_KEY in .env", file=sys.stderr)
        return 2

    api_base = os.getenv("MINIMAX_API_BASE", "https://api.minimaxi.com").rstrip("/")
    url = f"{api_base}/v1/chat/completions"
    payload = build_payload()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for run_number in range(1, args.runs + 1):
        result = run_once(
            run_number=run_number,
            url=url,
            api_key=api_key,
            payload=payload,
        )
        results.append(result)
        status = "PASS" if result["passed"] else "FAIL"
        print(
            f"RUN_{run_number:02d}_{status} "
            f"latency={result['latency_seconds']}s"
        )
        if not result["passed"]:
            print(result.get("error", "unknown error"), file=sys.stderr)

    passed_runs = sum(1 for result in results if result["passed"])
    summary = {
        "requested_model": payload["model"],
        "total_runs": args.runs,
        "passed_runs": passed_runs,
        "pass_rate": passed_runs / args.runs,
        "usage": sum_usage(results),
        "results": results,
    }
    SUMMARY_FILE.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved: {SUMMARY_FILE}")
    return 0 if passed_runs == args.runs else 1


if __name__ == "__main__":
    raise SystemExit(main())
