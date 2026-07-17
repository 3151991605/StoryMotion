from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from storymotion.models import ScreenplayPackage, ShotPackage, StoryMotionBundle
from storymotion.providers import FallbackShotProvider, RuleShotProvider
from storymotion.providers.minimax_shot_provider import (
    MiniMaxProtocolError,
    MiniMaxShotProvider,
    MiniMaxTransportError,
)


ROOT = Path(__file__).resolve().parents[1]
SCREENPLAY_FILE = (
    ROOT / "outputs/verification/screenplay/screenplay_package_repaired.json"
)


@pytest.fixture
def screenplay() -> ScreenplayPackage:
    return ScreenplayPackage.model_validate_json(
        SCREENPLAY_FILE.read_text(encoding="utf-8")
    )


def enrichment(shot_id: str, index: int) -> dict[str, Any]:
    return {
        "shot_id": shot_id,
        "shot_type": f"shot type {index}",
        "camera_movement": f"camera movement {index}",
        "visual_description": f"visual description {index}",
        "image_prompt": f"image prompt {index}",
        "video_prompt": f"video prompt {index}",
        "negative_prompt": "watermark, subtitles",
        "audio_prompt": f"audio prompt {index}",
    }


def test_visual_enrichment_request_excludes_spoken_text() -> None:
    fixture = ROOT / "tests/fixtures/valid_storymotion_bundle.json"
    bundle = StoryMotionBundle.model_validate_json(fixture.read_text(encoding="utf-8"))
    provider = MiniMaxShotProvider(RecordingTransport(response_for(["shot_001"])))
    skeleton = RuleShotProvider().generate(bundle.screenplay)

    payload = provider._build_payload(bundle.screenplay, skeleton)
    scenes = payload["messages"][1]["content"]
    request = json.loads(scenes)

    assert all(
        "dialogues" not in scene and "voiceover" not in scene
        for scene in request["screenplay"]["scenes"]
    )
    system = payload["messages"][0]["content"]
    assert "Do not add dialogue" in system


def response_for(
    shot_ids: list[str],
    *,
    finish_reason: str = "stop",
    reasoning: bool = False,
) -> dict[str, Any]:
    content = json.dumps(
        {
            "shots": [
                enrichment(shot_id, index)
                for index, shot_id in enumerate(shot_ids, start=1)
            ]
        },
        ensure_ascii=False,
    )
    if reasoning:
        content = f"<think>private reasoning</think>\n```json\n{content}\n```"
    return {
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {"content": content},
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 200,
            "total_tokens": 300,
        },
    }


class RecordingTransport:
    def __init__(self, response: dict[str, Any] | Exception) -> None:
        self.response = response
        self.calls: list[tuple[dict[str, Any], float]] = []

    def complete(
        self, payload: dict[str, Any], *, timeout: float
    ) -> dict[str, Any]:
        self.calls.append((payload, timeout))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def expected_rule_package(screenplay: ScreenplayPackage) -> ShotPackage:
    return RuleShotProvider(max_shot_duration=10).generate(screenplay)


def test_sends_one_bounded_request_and_preserves_structure(
    screenplay: ScreenplayPackage,
) -> None:
    expected = expected_rule_package(screenplay)
    ids = [shot.shot_id for shot in expected.shots]
    transport = RecordingTransport(response_for(ids))
    provider = MiniMaxShotProvider(
        transport,
        model="MiniMax-M3",
        request_timeout=42,
        max_completion_tokens=4096,
    )

    actual = provider.generate(screenplay)

    assert len(transport.calls) == 1
    payload, timeout = transport.calls[0]
    assert timeout == 42
    assert payload["model"] == "MiniMax-M3"
    assert payload["stream"] is False
    assert payload["temperature"] == 0.2
    assert payload["max_completion_tokens"] == 4096
    prompt = payload["messages"][1]["content"]
    assert all(shot_id in prompt for shot_id in ids)
    assert all(scene.scene_id in prompt for scene in screenplay.scenes)
    assert [shot.shot_id for shot in actual.shots] == ids
    assert [shot.scene_id for shot in actual.shots] == [
        shot.scene_id for shot in expected.shots
    ]
    assert [shot.duration for shot in actual.shots] == [
        shot.duration for shot in expected.shots
    ]
    assert [shot.character_ids for shot in actual.shots] == [
        shot.character_ids for shot in expected.shots
    ]


def test_parses_reasoning_fence_and_restores_canonical_order(
    screenplay: ScreenplayPackage,
) -> None:
    expected = expected_rule_package(screenplay)
    ids = [shot.shot_id for shot in expected.shots]
    transport = RecordingTransport(response_for(list(reversed(ids)), reasoning=True))

    actual = MiniMaxShotProvider(transport).generate(screenplay)

    assert [shot.shot_id for shot in actual.shots] == ids
    assert actual.shots[0].visual_description == f"visual description {len(ids)}"


@pytest.mark.parametrize("case", ["missing", "duplicate", "unknown"])
def test_rejects_non_bijective_shot_ids_without_retry(
    screenplay: ScreenplayPackage, case: str
) -> None:
    ids = [
        shot.shot_id for shot in expected_rule_package(screenplay).shots
    ]
    if case == "missing":
        returned_ids = ids[:-1]
    elif case == "duplicate":
        returned_ids = ids[:-1] + [ids[0]]
    else:
        returned_ids = ids[:-1] + ["shot_999"]
    transport = RecordingTransport(response_for(returned_ids))

    with pytest.raises(MiniMaxProtocolError, match="shot IDs"):
        MiniMaxShotProvider(transport).generate(screenplay)

    assert len(transport.calls) == 1


def test_rejects_truncated_output_without_retry(
    screenplay: ScreenplayPackage,
) -> None:
    ids = [shot.shot_id for shot in expected_rule_package(screenplay).shots]
    transport = RecordingTransport(response_for(ids, finish_reason="length"))

    with pytest.raises(MiniMaxProtocolError, match="finish_reason"):
        MiniMaxShotProvider(transport).generate(screenplay)

    assert len(transport.calls) == 1


def test_rejects_invalid_json_without_retry(screenplay: ScreenplayPackage) -> None:
    transport = RecordingTransport(
        {
            "choices": [
                {"finish_reason": "stop", "message": {"content": "not JSON"}}
            ]
        }
    )

    with pytest.raises(MiniMaxProtocolError, match="JSON"):
        MiniMaxShotProvider(transport).generate(screenplay)

    assert len(transport.calls) == 1


def test_propagates_classified_transport_failure(
    screenplay: ScreenplayPackage,
) -> None:
    transport = RecordingTransport(MiniMaxTransportError("service unavailable"))

    with pytest.raises(MiniMaxTransportError, match="service unavailable"):
        MiniMaxShotProvider(transport).generate(screenplay)

    assert len(transport.calls) == 1


class BuggyProvider:
    def generate(self, screenplay: ScreenplayPackage) -> ShotPackage:
        raise RuntimeError("programming error")


def test_configured_fallback_handles_minimax_failure(
    screenplay: ScreenplayPackage,
) -> None:
    primary = MiniMaxShotProvider(
        RecordingTransport(MiniMaxTransportError("service unavailable"))
    )
    fallback = RuleShotProvider()
    provider = FallbackShotProvider(
        primary,
        fallback,
        fallback_on=(MiniMaxTransportError,),
    )

    assert provider.generate(screenplay) == fallback.generate(screenplay)


def test_configured_fallback_does_not_hide_unrelated_errors(
    screenplay: ScreenplayPackage,
) -> None:
    provider = FallbackShotProvider(
        BuggyProvider(),
        RuleShotProvider(),
        fallback_on=(MiniMaxTransportError,),
    )

    with pytest.raises(RuntimeError, match="programming error"):
        provider.generate(screenplay)
