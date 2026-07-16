from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from storymotion.models import ScreenplayPackage
from storymotion.providers import MiniMaxTransportError, RuleShotProvider


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import verify_minimax_shot_provider as probe  # noqa: E402


SCREENPLAY_FILE = (
    ROOT / "outputs/verification/screenplay/screenplay_package_repaired.json"
)


class ProbeTransport:
    def __init__(self, response: dict[str, Any] | Exception) -> None:
        self.response = response
        self.calls = 0

    def complete(
        self, payload: dict[str, Any], *, timeout: float
    ) -> dict[str, Any]:
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def load_screenplay() -> ScreenplayPackage:
    return ScreenplayPackage.model_validate_json(
        SCREENPLAY_FILE.read_text(encoding="utf-8")
    )


def valid_response(screenplay: ScreenplayPackage) -> dict[str, Any]:
    shots = RuleShotProvider().generate(screenplay).shots
    return {
        "model": "MiniMax-M3",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps(
                        {
                            "shots": [
                                {
                                    "shot_id": shot.shot_id,
                                    "shot_type": "medium",
                                    "camera_movement": "slow push",
                                    "visual_description": "validated visual",
                                    "image_prompt": "validated image prompt",
                                    "video_prompt": "validated video prompt",
                                    "negative_prompt": None,
                                    "audio_prompt": None,
                                }
                                for shot in shots
                            ]
                        }
                    )
                },
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


def test_probe_makes_exactly_one_request_and_returns_valid_package() -> None:
    screenplay = load_screenplay()
    transport = ProbeTransport(valid_response(screenplay))

    summary, package = probe.run_probe(screenplay, transport, timeout=30)

    assert transport.calls == 1
    assert summary["max_requests"] == 1
    assert summary["requests_made"] == 1
    assert summary["max_completion_tokens"] == 8192
    assert summary["passed"] is True
    assert summary["finish_reason"] == "stop"
    assert summary["usage"]["total_tokens"] == 30
    assert package is not None
    assert package.total_shot_duration == screenplay.target_duration


def test_probe_redacts_secret_and_does_not_retry_on_failure() -> None:
    screenplay = load_screenplay()
    secret = "sk-test-do-not-write"
    transport = ProbeTransport(MiniMaxTransportError(f"failure {secret}"))

    summary, package = probe.run_probe(
        screenplay,
        transport,
        timeout=30,
        secrets=(secret,),
    )

    serialized = json.dumps(summary)
    assert transport.calls == 1
    assert summary["passed"] is False
    assert summary["requests_made"] == 1
    assert secret not in serialized
    assert "[REDACTED]" in serialized
    assert package is None
