"""Small, dependency-free client for OpenAI-compatible text generation APIs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class TextGenerationError(RuntimeError):
    """The configured text model could not return a usable response."""


class ChatClient(Protocol):
    def complete(self, *, system: str, user: str) -> str: ...


@dataclass(frozen=True)
class OpenAICompatibleChatClient:
    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: float = 120.0
    use_json_response_format: bool = True
    max_completion_tokens: int | None = None
    extra_payload: dict[str, Any] | None = None

    def complete(self, *, system: str, user: str) -> str:
        if not self.api_key.strip() or not self.model.strip():
            raise ValueError("api_key and model must not be empty")
        endpoint = self.base_url.rstrip("/") + "/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.use_json_response_format:
            payload["response_format"] = {"type": "json_object"}
        if self.max_completion_tokens is not None:
            payload["max_completion_tokens"] = self.max_completion_tokens
        if self.extra_payload:
            reserved = set(payload).intersection(self.extra_payload)
            if reserved:
                raise ValueError(
                    f"extra_payload cannot override reserved fields: {sorted(reserved)}"
                )
            payload.update(self.extra_payload)
        request = Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(4_000_000)
        except HTTPError as exc:
            detail = exc.read(2000).decode("utf-8", errors="replace")
            raise TextGenerationError(f"text model HTTP {exc.code}: {detail}") from exc
        except (URLError, OSError, TimeoutError) as exc:
            raise TextGenerationError(f"text model request failed: {exc}") from exc
        try:
            data: dict[str, Any] = json.loads(raw)
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise TextGenerationError("text model returned an invalid chat response") from exc
        if not isinstance(content, str) or not content.strip():
            raise TextGenerationError("text model returned empty content")
        return content
