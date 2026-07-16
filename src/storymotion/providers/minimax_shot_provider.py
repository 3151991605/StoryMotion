from __future__ import annotations

import json
import re
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import Field, ValidationError

from storymotion.models import ScreenplayPackage, Shot, ShotPackage
from storymotion.models.base import StrictModel

from .rule_shot_provider import DEFAULT_NEGATIVE_PROMPT, RuleShotProvider


MAX_RESPONSE_BYTES = 2_000_000


class MiniMaxShotProviderError(RuntimeError):
    """Base class for expected failures in bounded MiniMax shot generation."""


class MiniMaxTransportError(MiniMaxShotProviderError):
    """MiniMax could not be reached or returned a transport-level failure."""


class MiniMaxProtocolError(MiniMaxShotProviderError):
    """MiniMax returned a response that cannot be safely assembled."""


class ShotEnrichment(StrictModel):
    shot_id: str = Field(min_length=1, max_length=100)
    shot_type: str = Field(min_length=1, max_length=100)
    camera_movement: str = Field(min_length=1, max_length=200)
    visual_description: str = Field(min_length=1, max_length=3000)
    image_prompt: str = Field(min_length=1, max_length=5000)
    video_prompt: str = Field(min_length=1, max_length=5000)
    negative_prompt: str | None = Field(default=None, max_length=3000)
    audio_prompt: str | None = Field(default=None, max_length=3000)


class ShotEnrichmentPackage(StrictModel):
    shots: list[ShotEnrichment] = Field(min_length=1, max_length=60)


class MiniMaxChatTransport(Protocol):
    def complete(
        self, payload: dict[str, Any], *, timeout: float
    ) -> dict[str, Any]: ...


class UrllibMiniMaxChatTransport:
    """Bounded OpenAI-compatible JSON transport for the MiniMax platform."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.minimax.chat",
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key must not be empty")
        normalized = base_url.rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("base_url must use http or https")
        self._api_key = api_key
        self._endpoint = f"{normalized}/v1/chat/completions"

    def complete(
        self, payload: dict[str, Any], *, timeout: float
    ) -> dict[str, Any]:
        request = Request(
            self._endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise MiniMaxTransportError(
                f"MiniMax HTTP request failed with status {exc.code}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise MiniMaxTransportError(
                f"MiniMax request failed: {type(exc).__name__}"
            ) from exc

        if len(raw) > MAX_RESPONSE_BYTES:
            raise MiniMaxProtocolError("MiniMax response exceeds 2 MB")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MiniMaxProtocolError("MiniMax returned invalid response JSON") from exc
        if not isinstance(decoded, dict):
            raise MiniMaxProtocolError("MiniMax response JSON must be an object")
        return decoded


class MiniMaxShotProvider:
    """Enriches a deterministic shot skeleton with exactly one model request."""

    def __init__(
        self,
        transport: MiniMaxChatTransport,
        *,
        model: str = "MiniMax-M3",
        max_shot_duration: float = 10.0,
        request_timeout: float = 120.0,
        max_completion_tokens: int = 8192,
        temperature: float = 0.2,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be empty")
        if request_timeout <= 0:
            raise ValueError("request_timeout must be positive")
        if not 256 <= max_completion_tokens <= 32768:
            raise ValueError("max_completion_tokens must be between 256 and 32768")
        if not 0 <= temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        self.transport = transport
        self.model = model
        self.request_timeout = float(request_timeout)
        self.max_completion_tokens = int(max_completion_tokens)
        self.temperature = float(temperature)
        self._skeleton_provider = RuleShotProvider(
            max_shot_duration=max_shot_duration
        )

    def generate(self, screenplay: ScreenplayPackage) -> ShotPackage:
        skeleton = self._skeleton_provider.generate(screenplay)
        payload = self._build_payload(screenplay, skeleton)
        response = self.transport.complete(payload, timeout=self.request_timeout)
        enrichments = self._parse_response(response)
        enrichment_by_id = self._validate_shot_ids(skeleton, enrichments)

        shots = []
        for structural_shot in skeleton.shots:
            creative = enrichment_by_id[structural_shot.shot_id]
            shots.append(
                Shot(
                    shot_id=structural_shot.shot_id,
                    scene_id=structural_shot.scene_id,
                    duration=structural_shot.duration,
                    character_ids=structural_shot.character_ids,
                    shot_type=creative.shot_type,
                    camera_movement=creative.camera_movement,
                    visual_description=creative.visual_description,
                    image_prompt=creative.image_prompt,
                    video_prompt=creative.video_prompt,
                    negative_prompt=(
                        creative.negative_prompt
                        or structural_shot.negative_prompt
                        or DEFAULT_NEGATIVE_PROMPT
                    ),
                    audio_prompt=(
                        creative.audio_prompt or structural_shot.audio_prompt
                    ),
                )
            )
        return ShotPackage(
            title=screenplay.title,
            target_duration=screenplay.target_duration,
            shots=shots,
        )

    def _build_payload(
        self, screenplay: ScreenplayPackage, skeleton: ShotPackage
    ) -> dict[str, Any]:
        screenplay_context = {
            "title": screenplay.title,
            "characters": [
                {
                    "id": character.id,
                    "name": character.name,
                    "visual_prompt_en": character.visual_prompt_en,
                }
                for character in screenplay.characters
            ],
            "locations": [location.model_dump() for location in screenplay.locations],
            "scenes": [scene.model_dump() for scene in screenplay.scenes],
        }
        immutable_shots = [
            {
                "shot_id": shot.shot_id,
                "scene_id": shot.scene_id,
                "duration": shot.duration,
                "character_ids": shot.character_ids,
            }
            for shot in skeleton.shots
        ]
        request_document = {
            "screenplay": screenplay_context,
            "immutable_shots": immutable_shots,
            "required_output": {
                "shots": [
                    {
                        "shot_id": "copy an immutable shot_id exactly",
                        "shot_type": "non-empty string",
                        "camera_movement": "non-empty string",
                        "visual_description": "non-empty string",
                        "image_prompt": "English image-generation prompt",
                        "video_prompt": "English video-generation prompt",
                        "negative_prompt": "string or null",
                        "audio_prompt": "string or null",
                    }
                ]
            },
        }
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a storyboard prompt designer. Return one JSON "
                        "object only. Enrich every immutable shot exactly once. "
                        "Never add, remove, rename, or duplicate shot IDs. Do not "
                        "return scene_id, duration, or character_ids. Preserve "
                        "visual continuity and write production-ready prompts."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        request_document, ensure_ascii=False, separators=(",", ":")
                    ),
                },
            ],
            "stream": False,
            "temperature": self.temperature,
            "max_completion_tokens": self.max_completion_tokens,
        }

    @staticmethod
    def _parse_response(response: dict[str, Any]) -> list[ShotEnrichment]:
        try:
            choice = response["choices"][0]
            finish_reason = choice["finish_reason"]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise MiniMaxProtocolError("MiniMax response envelope is invalid") from exc
        if finish_reason != "stop":
            raise MiniMaxProtocolError(
                f"MiniMax finish_reason must be stop, got {finish_reason!r}"
            )
        if not isinstance(content, str) or not content.strip():
            raise MiniMaxProtocolError("MiniMax response content is empty")

        without_reasoning = re.sub(
            r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE
        )
        object_start = without_reasoning.find("{")
        if object_start < 0:
            raise MiniMaxProtocolError("MiniMax content does not contain a JSON object")
        try:
            decoded, _ = json.JSONDecoder().raw_decode(without_reasoning[object_start:])
        except json.JSONDecodeError as exc:
            raise MiniMaxProtocolError("MiniMax content contains invalid JSON") from exc
        try:
            package = ShotEnrichmentPackage.model_validate(decoded)
        except ValidationError as exc:
            raise MiniMaxProtocolError(
                "MiniMax shot enrichment schema is invalid: "
                f"{exc.errors(include_url=False)}"
            ) from exc
        return package.shots

    @staticmethod
    def _validate_shot_ids(
        skeleton: ShotPackage, enrichments: list[ShotEnrichment]
    ) -> dict[str, ShotEnrichment]:
        expected_ids = [shot.shot_id for shot in skeleton.shots]
        returned_ids = [shot.shot_id for shot in enrichments]
        if len(returned_ids) != len(set(returned_ids)):
            raise MiniMaxProtocolError("MiniMax shot IDs contain duplicates")
        if set(returned_ids) != set(expected_ids):
            missing = sorted(set(expected_ids) - set(returned_ids))
            unknown = sorted(set(returned_ids) - set(expected_ids))
            raise MiniMaxProtocolError(
                f"MiniMax shot IDs do not match skeleton; missing={missing}, "
                f"unknown={unknown}"
            )
        return {shot.shot_id: shot for shot in enrichments}
