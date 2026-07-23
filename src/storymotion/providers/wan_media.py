"""Alibaba Model Studio Wan image generation provider."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from pydantic import ValidationError

from storymotion.models import GeneratedImage, ImageGenerationRequest


MAX_JSON_RESPONSE_BYTES = 4_000_000
MAX_REQUEST_BYTES = 45_000_000
MAX_IMAGE_BYTES = 20_000_000
WAN_GENERATION_PATH = "/api/v1/services/aigc/multimodal-generation/generation"

WAN_1K_SIZES = {
    "1:1": "1024*1024",
    "16:9": "1365*768",
    "4:3": "1182*886",
    "3:2": "1254*836",
    "2:3": "836*1254",
    "3:4": "886*1182",
    "9:16": "768*1365",
    "21:9": "1564*670",
}


class WanMediaError(RuntimeError):
    """Base class for expected Wan image failures."""


class WanMediaTransportError(WanMediaError):
    """The Alibaba endpoint or result file could not be reached safely."""


class WanMediaProtocolError(WanMediaError):
    """The Alibaba response did not satisfy the Wan image contract."""


def _is_official_api_host(hostname: str) -> bool:
    return hostname == "dashscope.aliyuncs.com" or hostname.endswith(
        ".cn-beijing.maas.aliyuncs.com"
    )


def _validate_wan_download_url(url: str) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not hostname.startswith("dashscope-")
        or ".oss-" not in hostname
        or not hostname.endswith(".aliyuncs.com")
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
    ):
        raise WanMediaTransportError(
            "download URL is not an approved Alibaba DashScope result OSS HTTPS URL "
            f"(scheme={parsed.scheme!r}, host={hostname!r})"
        )


class _WanRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_wan_download_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _image_type(raw: bytes) -> str | None:
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


class WanMediaTransport(Protocol):
    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]: ...

    def download(
        self,
        url: str,
        output_file: Path,
        *,
        timeout: float,
        max_bytes: int,
    ) -> Path: ...


class UrllibWanMediaTransport:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://dashscope.aliyuncs.com",
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key must not be empty")
        normalized = base_url.rstrip("/")
        parsed = urlparse(normalized)
        hostname = (parsed.hostname or "").lower()
        if (
            parsed.scheme != "https"
            or not _is_official_api_host(hostname)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or parsed.path not in ("", "/")
        ):
            raise ValueError("base_url must be an official Alibaba Model Studio HTTPS host")
        self._api_key = api_key
        self._base_url = normalized

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if len(body) > MAX_REQUEST_BYTES:
            raise WanMediaProtocolError("Wan request exceeds 45 MB")
        request = Request(
            f"{self._base_url}{path}",
            data=body,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(MAX_JSON_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            detail = exc.read(2000).decode("utf-8", errors="replace")
            raise WanMediaTransportError(
                f"Wan HTTP request failed with status {exc.code}: {detail}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise WanMediaTransportError(
                f"Wan request failed: {type(exc).__name__}"
            ) from exc
        if len(raw) > MAX_JSON_RESPONSE_BYTES:
            raise WanMediaProtocolError("Wan JSON response exceeds 4 MB")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WanMediaProtocolError("Wan returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise WanMediaProtocolError("Wan JSON response must be an object")
        return decoded

    def download(
        self,
        url: str,
        output_file: Path,
        *,
        timeout: float,
        max_bytes: int,
    ) -> Path:
        _validate_wan_download_url(url)
        if timeout <= 0 or max_bytes <= 0:
            raise ValueError("download timeout and max_bytes must be positive")
        request = Request(url, headers={"Accept": "image/*"}, method="GET")
        try:
            opener = build_opener(_WanRedirectHandler())
            with opener.open(request, timeout=timeout) as response:
                _validate_wan_download_url(response.geturl())
                raw = response.read(max_bytes + 1)
        except HTTPError as exc:
            raise WanMediaTransportError(
                f"Wan image download failed with status {exc.code}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise WanMediaTransportError(
                f"Wan image download failed: {type(exc).__name__}"
            ) from exc
        if len(raw) > max_bytes:
            raise WanMediaProtocolError("Wan image exceeds configured size limit")
        if _image_type(raw) is None:
            raise WanMediaProtocolError("Wan returned an unsupported image format")
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_file.with_suffix(output_file.suffix + ".part")
        temporary.write_bytes(raw)
        temporary.replace(output_file)
        return output_file


class WanImageProvider:
    max_reference_images = 9

    def __init__(
        self,
        transport: WanMediaTransport,
        *,
        model: str = "wan2.7-image-pro",
        request_timeout: float = 300.0,
        download_timeout: float = 120.0,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be empty")
        self.transport = transport
        self.model = model
        self.request_timeout = request_timeout
        self.download_timeout = download_timeout

    def generate(
        self, request: ImageGenerationRequest, *, output_file: Path
    ) -> GeneratedImage:
        content: list[dict[str, str]] = []
        references = list(request.reference_images)
        if request.reference_image is not None:
            references.insert(0, request.reference_image)
        for reference in dict.fromkeys(references):
            content.append({"image": reference})
        content.append({"text": request.prompt})
        parameters: dict[str, Any] = {
            "size": WAN_1K_SIZES[request.aspect_ratio],
            "n": 1,
            "watermark": False,
        }
        if request.seed is not None:
            parameters["seed"] = request.seed
        if not references:
            parameters["thinking_mode"] = True
        payload = {
            "model": self.model,
            "input": {"messages": [{"role": "user", "content": content}]},
            "parameters": parameters,
        }
        raw = self.transport.request_json(
            "POST",
            WAN_GENERATION_PATH,
            payload=payload,
            timeout=self.request_timeout,
        )
        code = raw.get("code")
        if code:
            message = raw.get("message", "unknown error")
            raise WanMediaProtocolError(f"Wan API error {code}: {message}")
        request_id = raw.get("request_id") or raw.get("requestId")
        try:
            choices = raw["output"]["choices"]
            result_content = choices[0]["message"]["content"]
            image_url = next(
                item["image"]
                for item in result_content
                if item.get("type") == "image"
            )
        except (KeyError, IndexError, StopIteration, TypeError) as exc:
            raise WanMediaProtocolError("Wan response is missing an image URL") from exc
        if not isinstance(request_id, str) or not request_id:
            raise WanMediaProtocolError("Wan response is missing request_id")
        if not isinstance(image_url, str) or not image_url:
            raise WanMediaProtocolError("Wan image URL is invalid")
        output = self.transport.download(
            image_url,
            Path(output_file),
            timeout=self.download_timeout,
            max_bytes=MAX_IMAGE_BYTES,
        )
        media_type = _image_type(output.read_bytes())
        if media_type is None:
            raise WanMediaProtocolError("downloaded Wan image format is invalid")
        try:
            return GeneratedImage(
                provider="wan",
                model=self.model,
                request_id=request_id,
                path=output,
                media_type=media_type,
            )
        except ValidationError as exc:
            raise WanMediaProtocolError("Wan image metadata is invalid") from exc
