"""Run one bounded MiniMax-M3 storyboard-enrichment request with no retry."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from storymotion.models import ScreenplayPackage, ShotPackage
from storymotion.providers import (
    MiniMaxShotProvider,
    MiniMaxShotProviderError,
    UrllibMiniMaxChatTransport,
)
from storymotion.providers.minimax_shot_provider import MiniMaxChatTransport
from verify_minimax_access import ENV_FILE, load_local_env


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCREENPLAY_FILE = (
    ROOT / "outputs/verification/screenplay/screenplay_package_repaired.json"
)
SUMMARY_FILE = ROOT / "outputs/verification/minimax_shot_provider_summary.json"
PACKAGE_FILE = ROOT / "outputs/verification/minimax_shot_provider_package.json"


class ObservingTransport:
    """Records non-secret response metadata without changing request behavior."""

    def __init__(self, inner: MiniMaxChatTransport) -> None:
        self.inner = inner
        self.calls = 0
        self.last_response: dict[str, Any] | None = None

    def complete(
        self, payload: dict[str, Any], *, timeout: float
    ) -> dict[str, Any]:
        self.calls += 1
        response = self.inner.complete(payload, timeout=timeout)
        self.last_response = response
        return response


def redact_text(value: str, secrets: tuple[str, ...]) -> str:
    redacted = value
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


def run_probe(
    screenplay: ScreenplayPackage,
    transport: MiniMaxChatTransport,
    *,
    timeout: float,
    model: str = "MiniMax-M3",
    max_completion_tokens: int = 8192,
    secrets: tuple[str, ...] = (),
) -> tuple[dict[str, Any], ShotPackage | None]:
    observed = ObservingTransport(transport)
    provider = MiniMaxShotProvider(
        observed,
        model=model,
        request_timeout=timeout,
        max_completion_tokens=max_completion_tokens,
    )
    started = time.perf_counter()
    package: ShotPackage | None = None
    error: str | None = None
    try:
        package = provider.generate(screenplay)
    except MiniMaxShotProviderError as exc:
        error = redact_text(str(exc), secrets)

    response = observed.last_response or {}
    choices = response.get("choices")
    first_choice = choices[0] if isinstance(choices, list) and choices else {}
    summary: dict[str, Any] = {
        "requested_model": model,
        "response_model": response.get("model"),
        "input_screenplay": str(DEFAULT_SCREENPLAY_FILE.relative_to(ROOT)),
        "timeout_seconds": timeout,
        "max_completion_tokens": max_completion_tokens,
        "max_requests": 1,
        "requests_made": observed.calls,
        "automatic_retries": 0,
        "passed": package is not None,
        "finish_reason": (
            first_choice.get("finish_reason")
            if isinstance(first_choice, dict)
            else None
        ),
        "usage": response.get("usage", {}),
        "latency_seconds": round(time.perf_counter() - started, 3),
        "error": error,
    }
    if package is not None:
        summary.update(
            {
                "shot_count": len(package.shots),
                "total_shot_duration": package.total_shot_duration,
                "target_duration": package.target_duration,
                "structural_validation": "passed",
            }
        )
    return summary, package


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenplay", type=Path, default=DEFAULT_SCREENPLAY_FILE)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-completion-tokens", type=int, default=8192)
    args = parser.parse_args(argv)
    if not 30 <= args.timeout <= 300:
        parser.error("--timeout must be between 30 and 300 seconds")
    if not 1024 <= args.max_completion_tokens <= 16384:
        parser.error("--max-completion-tokens must be between 1024 and 16384")

    load_local_env(ENV_FILE)
    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if not api_key:
        print("Missing MINIMAX_API_KEY in .env", file=sys.stderr)
        return 2
    try:
        screenplay = ScreenplayPackage.model_validate_json(
            args.screenplay.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as exc:
        print(f"Invalid screenplay input: {exc}", file=sys.stderr)
        return 2

    base_url = os.getenv("MINIMAX_API_BASE", "https://api.minimaxi.com")
    transport = UrllibMiniMaxChatTransport(api_key=api_key, base_url=base_url)
    summary, package = run_probe(
        screenplay,
        transport,
        timeout=args.timeout,
        max_completion_tokens=args.max_completion_tokens,
        secrets=(api_key,),
    )
    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if package is not None:
        PACKAGE_FILE.write_text(
            json.dumps(package.model_dump(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        summary["output_file"] = str(PACKAGE_FILE.relative_to(ROOT))
    SUMMARY_FILE.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Saved: {SUMMARY_FILE}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
