"""Verify an isolated PenShot runtime against MiniMax without exposing secrets."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any


ALLOWED_ENV_KEYS = {"MINIMAX_API_KEY", "MINIMAX_API_BASE"}


def read_allowed_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in ALLOWED_ENV_KEYS:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def minimax_openai_base(api_base: str) -> str:
    normalized = api_base.rstrip("/")
    return normalized if normalized.endswith("/v1") else f"{normalized}/v1"


def redact(value: str, secrets: list[str], limit: int = 2_000) -> str:
    redacted = value
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "***REDACTED***")
    return redacted[:limit]


def isolated_work_dir(output_file: Path) -> Path:
    path = output_file.parent / "penshot_runtime" / "work" / "level_1" / "level_2"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_probe(
    *,
    mode: str,
    env_file: Path,
    output_file: Path,
    model: str,
    max_tokens: int,
    timeout: float,
) -> dict[str, Any]:
    allowed = read_allowed_env(env_file)
    api_key = allowed.get("MINIMAX_API_KEY", "")
    api_base = allowed.get("MINIMAX_API_BASE", "https://api.minimaxi.com")
    if mode in {"client", "invoke", "rule-workflow"} and not api_key:
        raise RuntimeError("MINIMAX_API_KEY is missing")

    for key in (
        "OPENAI_API_KEY",
        "DEEPSEEK_API_KEY",
        "DASHSCOPE_API_KEY",
        "LLM_API_KEY",
    ):
        os.environ.pop(key, None)
    os.environ["MINIMAX_API_BASE"] = api_base
    os.environ["REDIS_CONNECT_TIMEOUT"] = "0.25"
    os.environ["REDIS_SOCKET_TIMEOUT"] = "0.25"
    os.environ["REDIS_RETRY_ON_TIMEOUT"] = "false"
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    work_dir = isolated_work_dir(output_file)
    os.chdir(work_dir)
    discoverable_env = any(
        (parent / ".env").is_file() for parent in list(work_dir.parents)[:2]
    )

    started = time.monotonic()
    summary: dict[str, Any] = {
        "mode": mode,
        "python_version": sys.version.split()[0],
        "model": model,
        "api_base": minimax_openai_base(api_base),
        "api_key_present": bool(api_key),
        "api_key_stored": False,
        "working_directory": str(work_dir),
        "env_file_discoverable_within_two_parents": discoverable_env,
        "success": False,
    }

    try:
        import penshot
        from pydantic import SecretStr
        from penshot.config.config_models import LLMBaseConfig
        from penshot.neopen.client.client_config import (
            ClientType,
            detect_ai_provider_by_url,
        )
        from penshot.neopen.shot_config import ShotConfig

        provider = detect_ai_provider_by_url(minimax_openai_base(api_base))
        summary.update(
            {
                "penshot_runtime_version": penshot.__version__,
                "detected_provider": provider.value,
                "provider_is_openai": provider is ClientType.OPENAI,
                "import_passed": True,
            }
        )
        if mode == "import":
            summary["success"] = provider is ClientType.OPENAI
            return summary

        config = ShotConfig(
            llm=LLMBaseConfig(
                base_url=minimax_openai_base(api_base),
                model_name=model,
                api_key=SecretStr(api_key),
                temperature=0.1,
                timeout=timeout,
                max_tokens=max_tokens,
                max_retries=0,
            ),
            enable_llm=True,
            max_fragment_duration=10.0,
            auto_continue_on_human_intervention=True,
            human_intervention_mode="auto",
            workflow_timeout=int(timeout),
        )
        llm = config.get_llm_by_config()
        summary.update(
            {
                "client_construction_passed": llm is not None,
                "client_type": type(llm).__name__ if llm is not None else None,
            }
        )
        if mode == "client":
            summary["success"] = llm is not None and provider is ClientType.OPENAI
            return summary

        if mode == "rule-workflow":
            from penshot import PenshotFunction, ShotLanguage

            summary["warning"] = (
                "PenShot ScriptParserAgent ignores enable_llm=False; "
                "model calls may occur"
            )
            config.enable_llm = False
            config.max_total_loops = 8
            config.always_enhance = False
            config.enable_enhance = False
            config.ai_splitter_enabled = False
            config.checkpoint_mode = "memory"
            agent = PenshotFunction(
                config=config,
                language=ShotLanguage.ZH,
                max_concurrent=1,
                queue_size=4,
            )
            workflow_result = agent.breakdown_script(
                """场景一：雨夜旧车站，夜晚，持续10秒。
林辰站在昏黄路灯下，握紧一封旧信，雨水顺着外套滴落。
林辰（低声）：这一次，我不会错过真相。

场景二：候车室内，夜晚，持续10秒。
墙上的旧钟忽然倒转，林辰抬头，蓝色微光映亮他的脸。
旁白：时间留下了第二次机会。""",
                script_id="storymotion_rule_probe",
                wait_timeout=60,
            )
            status = getattr(workflow_result.status, "value", str(workflow_result.status))
            data = workflow_result.data or {}
            instructions = data.get("instructions", {}) if isinstance(data, dict) else {}
            fragments = (
                instructions.get("fragments", [])
                if isinstance(instructions, dict)
                else getattr(instructions, "fragments", [])
            )
            summary.update(
                {
                    "rule_workflow_passed": bool(workflow_result.success),
                    "task_id": workflow_result.task_id,
                    "task_status": status,
                    "fragment_count": len(fragments or []),
                    "processing_time_ms": workflow_result.processing_time_ms,
                    "workflow_error": redact(
                        workflow_result.error or "", [api_key]
                    ),
                    "success": bool(workflow_result.success),
                }
            )
            return summary

        if llm is None:
            raise RuntimeError("PenShot returned no LLM client")
        response = llm.invoke(
            "只回复 PENSHot_OK，不要解释。",
            config={"run_name": "storymotion-penshot-minimax-probe"},
        )
        content = response.content
        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        summary.update(
            {
                "invoke_passed": True,
                "response_nonempty": bool(content.strip()),
                "response_preview": redact(content.strip(), [api_key])[:200],
                "response_model": response.response_metadata.get("model_name"),
                "finish_reason": response.response_metadata.get("finish_reason"),
                "usage_metadata": response.usage_metadata,
                "success": bool(content.strip()),
            }
        )
        return summary
    except Exception as exc:
        summary.update(
            {
                "error_type": type(exc).__name__,
                "error": redact(str(exc), [api_key]),
                "traceback": redact(traceback.format_exc(), [api_key], limit=10_000),
            }
        )
        return summary
    finally:
        summary["elapsed_seconds"] = round(time.monotonic() - started, 3)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("import", "client", "invoke", "rule-workflow"),
        required=True,
    )
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="MiniMax-M3")
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument(
        "--acknowledge-penshot-ignores-disable-llm",
        action="store_true",
        help="Required for rule-workflow because PenShot still performs LLM calls.",
    )
    args = parser.parse_args()
    if (
        args.mode == "rule-workflow"
        and not args.acknowledge_penshot_ignores_disable_llm
    ):
        parser.error(
            "rule-workflow is not offline: PenShot ignores enable_llm=False; "
            "pass --acknowledge-penshot-ignores-disable-llm to proceed"
        )

    output_file = args.output.resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    summary = run_probe(
        mode=args.mode,
        env_file=args.env_file.resolve(),
        output_file=output_file,
        model=args.model,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
    )
    output_file.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
