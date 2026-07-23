from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from storymotion.models import ImageGenerationRequest
from storymotion.providers.wan_media import (
    UrllibWanMediaTransport,
    WanImageProvider,
    WanMediaProtocolError,
    WanMediaTransportError,
    _validate_wan_download_url,
)


class ScriptedTransport:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.calls: list[tuple[str, str, dict[str, Any], float]] = []
        self.downloads: list[tuple[str, Path, float, int]] = []

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        self.calls.append((method, path, payload, timeout))
        return self.response

    def download(
        self,
        url: str,
        output_file: Path,
        *,
        timeout: float,
        max_bytes: int,
    ) -> Path:
        self.downloads.append((url, output_file, timeout, max_bytes))
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(b"\x89PNG\r\n\x1a\nwan-image")
        return output_file


def success_response() -> dict[str, Any]:
    return {
        "request_id": "wan-request-1",
        "usage": {"image_count": 1, "size": "768*1365"},
        "output": {
            "finished": True,
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "image",
                                "image": (
                                    "https://dashscope-result-bj.oss-cn-beijing."
                                    "aliyuncs.com/result.png?Expires=1"
                                ),
                            }
                        ],
                    },
                }
            ],
        },
    }


def test_provider_maps_reference_request_to_wan_payload(tmp_path: Path) -> None:
    transport = ScriptedTransport(success_response())
    provider = WanImageProvider(transport, model="wan2.7-image-pro")
    output = tmp_path / "shot.png"

    artifact = provider.generate(
        ImageGenerationRequest(
            prompt="cinematic frame",
            aspect_ratio="9:16",
            reference_images=[
                "data:image/png;base64,AAAA",
                "data:image/png;base64,BBBB",
            ],
            seed=42,
        ),
        output_file=output,
    )

    assert artifact.provider == "wan"
    assert artifact.model == "wan2.7-image-pro"
    assert artifact.request_id == "wan-request-1"
    assert artifact.path == output
    assert artifact.media_type == "image/png"
    method, path, payload, timeout = transport.calls[0]
    assert method == "POST"
    assert path == "/api/v1/services/aigc/multimodal-generation/generation"
    assert timeout == 300
    assert payload == {
        "model": "wan2.7-image-pro",
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": "data:image/png;base64,AAAA"},
                        {"image": "data:image/png;base64,BBBB"},
                        {"text": "cinematic frame"},
                    ],
                }
            ]
        },
        "parameters": {
            "size": "768*1365",
            "n": 1,
            "watermark": False,
            "seed": 42,
        },
    }
    assert len(transport.downloads) == 1


def test_provider_enables_thinking_for_text_to_image(tmp_path: Path) -> None:
    transport = ScriptedTransport(success_response())

    WanImageProvider(transport).generate(
        ImageGenerationRequest(prompt="identity anchor", aspect_ratio="1:1"),
        output_file=tmp_path / "identity.png",
    )

    parameters = transport.calls[0][2]["parameters"]
    assert parameters["size"] == "1024*1024"
    assert parameters["thinking_mode"] is True
    assert "seed" not in parameters


def test_provider_rejects_error_response_without_download(tmp_path: Path) -> None:
    transport = ScriptedTransport(
        {"request_id": "failed", "code": "InvalidParameter", "message": "bad input"}
    )

    with pytest.raises(WanMediaProtocolError, match="InvalidParameter"):
        WanImageProvider(transport).generate(
            ImageGenerationRequest(prompt="frame"),
            output_file=tmp_path / "frame.png",
        )

    assert not transport.downloads


def test_provider_rejects_missing_image_result(tmp_path: Path) -> None:
    transport = ScriptedTransport(
        {
            "request_id": "empty",
            "output": {"finished": True, "choices": []},
        }
    )

    with pytest.raises(WanMediaProtocolError, match="image URL"):
        WanImageProvider(transport).generate(
            ImageGenerationRequest(prompt="frame"),
            output_file=tmp_path / "frame.png",
        )


def test_transport_accepts_official_beijing_hosts() -> None:
    UrllibWanMediaTransport(
        api_key="secret",
        base_url="https://dashscope.aliyuncs.com",
    )
    UrllibWanMediaTransport(
        api_key="secret",
        base_url="https://ws-example.cn-beijing.maas.aliyuncs.com",
    )


def test_transport_rejects_unapproved_api_host() -> None:
    with pytest.raises(ValueError, match="official Alibaba"):
        UrllibWanMediaTransport(
            api_key="secret",
            base_url="https://127.0.0.1",
        )


def test_download_url_validation_rejects_non_oss_host() -> None:
    with pytest.raises(WanMediaTransportError, match="approved Alibaba"):
        _validate_wan_download_url("https://127.0.0.1/private.png")


@pytest.mark.parametrize(
    "url",
    [
        "https://dashscope-result-bj.oss-cn-beijing.aliyuncs.com/result.png?Expires=1",
        (
            "https://dashscope-result-wlcb-acdr-1.oss-cn-wulanchabu-acdr-1."
            "aliyuncs.com/result.png"
        ),
        "https://dashscope-result-sh.oss-cn-shanghai.aliyuncs.com/result.png",
        "https://dashscope-result-sz.oss-cn-shenzhen.aliyuncs.com/result.png",
        "https://dashscope-result-global.oss-accelerate.aliyuncs.com/result.png",
        "https://dashscope-result.oss-cn-beijing.aliyuncs.com/result.png",
        "https://dashscope-7c2c.oss-accelerate.aliyuncs.com/result.png",
    ],
)
def test_download_url_validation_accepts_dashscope_result_oss(url: str) -> None:
    _validate_wan_download_url(url)


def test_download_url_validation_rejects_unrelated_alibaba_oss() -> None:
    with pytest.raises(WanMediaTransportError, match="approved Alibaba"):
        _validate_wan_download_url(
            "https://unrelated-bucket.oss-cn-beijing.aliyuncs.com/result.png"
        )
