from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from storymotion.models import ScreenplayPackage, ShotPackage
from storymotion.providers import RuleShotProvider
from storymotion.providers.penshot_sidecar import (
    FallbackShotProvider,
    PenShotSidecarClient,
    PenShotSidecarProvider,
    SidecarProtocolError,
    SidecarTaskError,
    SidecarTimeoutError,
)


ROOT = Path(__file__).resolve().parents[1]
SCREENPLAY_FILE = (
    ROOT / "outputs/verification/screenplay/screenplay_package_repaired.json"
)
RESULT_FILE = ROOT / "tests/fixtures/penshot_fragments.json"


@pytest.fixture
def screenplay() -> ScreenplayPackage:
    return ScreenplayPackage.model_validate_json(
        SCREENPLAY_FILE.read_text(encoding="utf-8")
    )


@pytest.fixture
def raw_result() -> dict[str, Any]:
    return json.loads(RESULT_FILE.read_text(encoding="utf-8"))


class ScriptedTransport:
    def __init__(self, responses: list[dict[str, Any] | Exception]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, Any] | None, float]] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None,
        timeout: float,
    ) -> dict[str, Any]:
        self.calls.append((method, path, payload, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def test_submits_screenplay_and_returns_completed_result(
    screenplay: ScreenplayPackage, raw_result: dict[str, Any]
) -> None:
    transport = ScriptedTransport(
        [
            {"task_id": "task-1"},
            {"task_id": "task-1", "status": "processing"},
            {"task_id": "task-1", "status": "completed", "result": raw_result},
        ]
    )
    clock = Clock()
    client = PenShotSidecarClient(
        transport,
        poll_interval=0.25,
        overall_timeout=3,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    result = client.breakdown_screenplay(
        screenplay, project_id="project-1", language="zh", style="anime"
    )

    assert result == raw_result
    method, path, payload, timeout = transport.calls[0]
    assert (method, path) == ("POST", "/v1/storyboards")
    assert payload is not None
    assert payload["project_id"] == "project-1"
    assert payload["language"] == "zh"
    assert payload["style"] == "anime"
    assert "scene_001" in payload["script"]
    assert timeout == 3
    assert transport.calls[1][0:2] == ("GET", "/v1/tasks/task-1")


def test_rejects_completed_task_without_result(screenplay: ScreenplayPackage) -> None:
    client = PenShotSidecarClient(
        ScriptedTransport(
            [
                {"task_id": "task-1"},
                {"task_id": "task-1", "status": "completed"},
            ]
        )
    )

    with pytest.raises(SidecarProtocolError, match="completed.*result"):
        client.breakdown_screenplay(screenplay)


def test_raises_bounded_remote_task_error(screenplay: ScreenplayPackage) -> None:
    client = PenShotSidecarClient(
        ScriptedTransport(
            [
                {"task_id": "task-1"},
                {
                    "task_id": "task-1",
                    "status": "failed",
                    "error": "model unavailable",
                },
            ]
        )
    )

    with pytest.raises(SidecarTaskError, match="model unavailable"):
        client.breakdown_screenplay(screenplay)


def test_timeout_attempts_task_cancellation(screenplay: ScreenplayPackage) -> None:
    transport = ScriptedTransport(
        [
            {"task_id": "task-1"},
            {"task_id": "task-1", "status": "processing"},
            {"task_id": "task-1", "status": "processing"},
            {"task_id": "task-1", "status": "cancelled"},
        ]
    )
    clock = Clock()
    client = PenShotSidecarClient(
        transport,
        poll_interval=0.5,
        overall_timeout=0.75,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
    )

    with pytest.raises(SidecarTimeoutError, match="task-1"):
        client.breakdown_screenplay(screenplay)

    assert transport.calls[-1][0:2] == ("DELETE", "/v1/tasks/task-1")


def test_provider_adapts_sidecar_result(
    screenplay: ScreenplayPackage, raw_result: dict[str, Any]
) -> None:
    client = PenShotSidecarClient(
        ScriptedTransport(
            [
                {"task_id": "task-1"},
                {"task_id": "task-1", "status": "completed", "result": raw_result},
            ]
        )
    )

    package = PenShotSidecarProvider(client).generate(screenplay)

    assert isinstance(package, ShotPackage)
    assert package.total_shot_duration == screenplay.target_duration
    assert len(package.shots) == 6


class FailingProvider:
    def generate(self, screenplay: ScreenplayPackage) -> ShotPackage:
        raise SidecarTaskError("sidecar failed")


class BuggyProvider:
    def generate(self, screenplay: ScreenplayPackage) -> ShotPackage:
        raise RuntimeError("programming error")


def test_fallback_provider_uses_rule_provider_for_sidecar_failures(
    screenplay: ScreenplayPackage,
) -> None:
    provider = FallbackShotProvider(FailingProvider(), RuleShotProvider())

    assert provider.generate(screenplay) == RuleShotProvider().generate(screenplay)


def test_fallback_provider_handles_invalid_sidecar_storyboard(
    screenplay: ScreenplayPackage,
) -> None:
    client = PenShotSidecarClient(
        ScriptedTransport(
            [
                {"task_id": "task-1"},
                {
                    "task_id": "task-1",
                    "status": "completed",
                    "result": {"fragments": []},
                },
            ]
        )
    )
    primary = PenShotSidecarProvider(client)
    provider = FallbackShotProvider(primary, RuleShotProvider())

    assert provider.generate(screenplay) == RuleShotProvider().generate(screenplay)


def test_fallback_provider_does_not_hide_unrelated_errors(
    screenplay: ScreenplayPackage,
) -> None:
    provider = FallbackShotProvider(BuggyProvider(), RuleShotProvider())

    with pytest.raises(RuntimeError, match="programming error"):
        provider.generate(screenplay)
