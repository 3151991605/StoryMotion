from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

import storymotion.providers.minimax_media as media
from storymotion.providers.minimax_media import (
    MiniMaxMediaProtocolError,
    MiniMaxMediaTransportError,
    UrllibMiniMaxMediaTransport,
)


class FakeResponse:
    def __init__(self, body: bytes, *, final_url: str = "https://api.minimaxi.com"):
        self.body = io.BytesIO(body)
        self.final_url = final_url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size: int = -1) -> bytes:
        return self.body.read(size)

    def geturl(self) -> str:
        return self.final_url


def test_transport_sends_secret_only_in_authorization_header(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(json.dumps({"ok": True}).encode())

    monkeypatch.setattr(media, "urlopen", fake_urlopen)
    transport = UrllibMiniMaxMediaTransport(
        api_key="secret-key", base_url="https://api.minimaxi.com"
    )

    result = transport.request_json(
        "POST",
        "/v1/image_generation",
        payload={"prompt": "frame"},
        params=None,
        timeout=12,
    )

    request = captured["request"]
    assert result == {"ok": True}
    assert request.get_header("Authorization") == "Bearer secret-key"
    assert b"secret-key" not in request.data
    assert captured["timeout"] == 12


def test_transport_rejects_invalid_json(monkeypatch) -> None:
    monkeypatch.setattr(media, "urlopen", lambda *args, **kwargs: FakeResponse(b"no"))
    transport = UrllibMiniMaxMediaTransport(api_key="secret-key")

    with pytest.raises(MiniMaxMediaProtocolError, match="invalid JSON"):
        transport.request_json(
            "GET", "/v1/test", payload=None, params=None, timeout=10
        )


def test_download_rejects_unapproved_host_before_network(tmp_path: Path) -> None:
    transport = UrllibMiniMaxMediaTransport(api_key="secret-key")

    with pytest.raises(MiniMaxMediaTransportError, match="approved"):
        transport.download(
            "https://127.0.0.1/private.mp4",
            tmp_path / "video.mp4",
            timeout=10,
            max_bytes=1024,
        )


def test_transport_rejects_non_official_api_host() -> None:
    with pytest.raises(ValueError, match="official MiniMax"):
        UrllibMiniMaxMediaTransport(
            api_key="secret-key", base_url="https://127.0.0.1"
        )


def test_download_redirect_rejects_unapproved_host() -> None:
    handler = media._ApprovedRedirectHandler()

    with pytest.raises(MiniMaxMediaTransportError, match="approved"):
        handler.redirect_request(
            media.Request("https://filecdn.minimax.chat/output.mp4"),
            None,
            302,
            "Found",
            {},
            "https://127.0.0.1/private.mp4",
        )


def test_download_accepts_authenticated_minimax_aliyun_cdn_host() -> None:
    media._validate_approved_download_url(
        "https://public-cdn-video-data-algeng.oss-cn-wulanchabu.aliyuncs.com/video.mp4"
    )
