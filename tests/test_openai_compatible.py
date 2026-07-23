from __future__ import annotations

import json

import storymotion.providers.openai_compatible as compatible
from storymotion.providers import OpenAICompatibleChatClient


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, _size: int) -> bytes:
        return json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode()


def test_sends_provider_specific_payload_fields(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(compatible, "urlopen", fake_urlopen)
    client = OpenAICompatibleChatClient(
        api_key="test-key",
        model="MiniMax-M2.7",
        use_json_response_format=False,
        max_completion_tokens=8192,
        extra_payload={"reasoning_split": True},
    )

    assert client.complete(system="system", user="user") == "{}"
    assert captured["payload"]["reasoning_split"] is True
    assert captured["payload"]["max_completion_tokens"] == 8192
