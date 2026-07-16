"""Read-only MiniMax Token Plan access probe.

This script only queries subscription usage and the available model list. It
does not request text, image, audio, or video generation.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
SENSITIVE_PARTS = ("authorization", "api_key", "apikey", "secret", "token")


def load_local_env(path: Path) -> None:
    """Load simple KEY=VALUE pairs without overriding process variables."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def sanitize(value: Any) -> Any:
    """Redact fields that could contain credentials before printing."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if any(part in lowered for part in SENSITIVE_PARTS):
                result[str(key)] = "<redacted>"
            else:
                result[str(key)] = sanitize(item)
        return result
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def get_json(url: str, api_key: str) -> Any:
    request = Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "StoryMotion-Feasibility-Probe/0.1",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Non-JSON response: {body[:500]}") from exc


def main() -> int:
    load_local_env(ENV_FILE)

    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if not api_key:
        print(
            "Missing MINIMAX_API_KEY. Copy .env.example to .env and fill in "
            "your Token Plan subscription key locally.",
            file=sys.stderr,
        )
        return 2

    api_base = os.getenv("MINIMAX_API_BASE", "https://api.minimaxi.com").rstrip("/")
    account_base = os.getenv(
        "MINIMAX_ACCOUNT_BASE", "https://www.minimaxi.com"
    ).rstrip("/")

    checks = (
        ("token_plan_remains", f"{account_base}/v1/token_plan/remains"),
        ("available_models", f"{api_base}/v1/models"),
    )

    failed = False
    for name, url in checks:
        print(f"\n=== {name} ===")
        try:
            payload = get_json(url, api_key)
        except RuntimeError as exc:
            failed = True
            print(str(exc), file=sys.stderr)
            continue
        print(json.dumps(sanitize(payload), ensure_ascii=False, indent=2))

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
