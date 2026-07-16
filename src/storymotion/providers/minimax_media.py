from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen

from pydantic import ValidationError

from storymotion.models import (
    GeneratedImage,
    ImageGenerationRequest,
    MediaTaskStatus,
    VideoGenerationRequest,
    VideoResult,
    VideoTask,
)


MAX_JSON_RESPONSE_BYTES = 2_000_000
MAX_IMAGE_BYTES = 20_000_000
DEFAULT_MAX_VIDEO_BYTES = 250_000_000
APPROVED_DOWNLOAD_SUFFIXES = (
    ".minimax.chat",
    ".minimaxi.com",
    ".minimax.io",
    ".hailuoai.com",
)
APPROVED_DOWNLOAD_HOSTS = {
    "public-cdn-video-data-algeng.oss-cn-wulanchabu.aliyuncs.com",
}


def _validate_approved_download_url(url: str) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or not (
            hostname in APPROVED_DOWNLOAD_HOSTS
            or any(
                hostname.endswith(suffix)
                for suffix in APPROVED_DOWNLOAD_SUFFIXES
            )
        )
    ):
        raise MiniMaxMediaTransportError(
            "download URL is not an approved MiniMax/Hailuo HTTPS URL"
        )


class _ApprovedRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_approved_download_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class MiniMaxMediaError(RuntimeError):
    """Base class for expected MiniMax media failures."""


class MiniMaxMediaTransportError(MiniMaxMediaError):
    """The media endpoint or download could not be reached safely."""


class MiniMaxMediaProtocolError(MiniMaxMediaError):
    """A MiniMax response did not satisfy the expected contract."""


class MiniMaxAccountError(MiniMaxMediaError):
    """The account or quota rejected a media operation."""


class MiniMaxMediaTaskError(MiniMaxMediaError):
    """A media task is failed, incomplete, or unavailable."""


class MiniMaxMediaTransport(Protocol):
    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None,
        params: dict[str, str] | None,
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


class UrllibMiniMaxMediaTransport:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.minimaxi.com",
    ) -> None:
        if not api_key.strip():
            raise ValueError("api_key must not be empty")
        normalized = base_url.rstrip("/")
        parsed = urlparse(normalized)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"api.minimaxi.com", "api.minimax.io"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
        ):
            raise ValueError("base_url must be an official MiniMax HTTPS API host")
        self._api_key = api_key
        self._base_url = normalized

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None,
        params: dict[str, str] | None,
        timeout: float,
    ) -> dict[str, Any]:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        query = f"?{urlencode(params)}" if params else ""
        body = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            if len(body) > 32_000_000:
                raise MiniMaxMediaProtocolError("MiniMax request exceeds 32 MB")
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = Request(
            f"{self._base_url}{path}{query}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(MAX_JSON_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise MiniMaxMediaTransportError(
                f"MiniMax media HTTP request failed with status {exc.code}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise MiniMaxMediaTransportError(
                f"MiniMax media request failed: {type(exc).__name__}"
            ) from exc
        if len(raw) > MAX_JSON_RESPONSE_BYTES:
            raise MiniMaxMediaProtocolError("MiniMax JSON response exceeds 2 MB")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MiniMaxMediaProtocolError("MiniMax returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise MiniMaxMediaProtocolError("MiniMax JSON response must be an object")
        return decoded

    def download(
        self,
        url: str,
        output_file: Path,
        *,
        timeout: float,
        max_bytes: int,
    ) -> Path:
        _validate_approved_download_url(url)
        if timeout <= 0 or max_bytes <= 0:
            raise ValueError("download timeout and max_bytes must be positive")
        request = Request(url, headers={"Accept": "video/mp4"}, method="GET")
        try:
            opener = build_opener(_ApprovedRedirectHandler())
            with opener.open(request, timeout=timeout) as response:
                final_url = response.geturl()
                _validate_approved_download_url(final_url)
                raw = response.read(max_bytes + 1)
        except HTTPError as exc:
            raise MiniMaxMediaTransportError(
                f"MiniMax download failed with status {exc.code}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise MiniMaxMediaTransportError(
                f"MiniMax download failed: {type(exc).__name__}"
            ) from exc
        if len(raw) > max_bytes:
            raise MiniMaxMediaProtocolError("video download exceeds configured limit")
        if not raw:
            raise MiniMaxMediaProtocolError("video download is empty")
        if len(raw) < 12 or raw[4:8] != b"ftyp":
            raise MiniMaxMediaProtocolError("downloaded file is not an MP4 video")
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_file.with_suffix(output_file.suffix + ".part")
        temporary.write_bytes(raw)
        temporary.replace(output_file)
        return output_file

def _validate_base_response(raw: dict[str, Any]) -> None:
    base = raw.get("base_resp")
    if not isinstance(base, dict):
        raise MiniMaxMediaProtocolError("MiniMax response is missing base_resp")
    code = base.get("status_code")
    if not isinstance(code, int):
        raise MiniMaxMediaProtocolError("MiniMax base_resp status_code is invalid")
    if code == 0:
        return
    if code in {1004, 1008, 2049, 2056}:
        raise MiniMaxAccountError(f"MiniMax account rejected request: status {code}")
    raise MiniMaxMediaTaskError(f"MiniMax media request failed: status {code}")


def _image_type(raw: bytes) -> str | None:
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


class MiniMaxImageProvider:
    def __init__(
        self,
        transport: MiniMaxMediaTransport,
        *,
        model: str = "image-01",
        request_timeout: float = 120.0,
    ) -> None:
        self.transport = transport
        self.model = model
        self.request_timeout = request_timeout

    def generate(
        self, request: ImageGenerationRequest, *, output_file: Path
    ) -> GeneratedImage:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": request.prompt,
            "aspect_ratio": request.aspect_ratio,
            "response_format": "base64",
            "n": 1,
            "prompt_optimizer": False,
            "aigc_watermark": False,
        }
        if request.reference_image is not None:
            payload["subject_reference"] = [
                {"type": "character", "image_file": request.reference_image}
            ]
        if request.seed is not None:
            payload["seed"] = request.seed
        raw = self.transport.request_json(
            "POST",
            "/v1/image_generation",
            payload=payload,
            params=None,
            timeout=self.request_timeout,
        )
        _validate_base_response(raw)
        try:
            request_id = raw["id"]
            values = raw["data"]["image_base64"]
            encoded = values[0]
        except (KeyError, IndexError, TypeError) as exc:
            raise MiniMaxMediaProtocolError(
                "MiniMax image response payload is invalid"
            ) from exc
        if not isinstance(request_id, str) or not isinstance(encoded, str):
            raise MiniMaxMediaProtocolError("MiniMax image response types are invalid")
        try:
            image = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise MiniMaxMediaProtocolError("MiniMax image base64 is invalid") from exc
        if len(image) > MAX_IMAGE_BYTES:
            raise MiniMaxMediaProtocolError("MiniMax image exceeds 20 MB")
        media_type = _image_type(image)
        if media_type is None:
            raise MiniMaxMediaProtocolError("MiniMax returned an unsupported image format")
        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_file.with_suffix(output_file.suffix + ".part")
        temporary.write_bytes(image)
        temporary.replace(output_file)
        try:
            return GeneratedImage(
                provider="minimax",
                model=self.model,
                request_id=request_id,
                path=output_file,
                media_type=media_type,
            )
        except ValidationError as exc:
            raise MiniMaxMediaProtocolError(
                "MiniMax image artifact metadata is invalid"
            ) from exc


class HailuoVideoProvider:
    REMOTE_STATUSES = {
        "Preparing": MediaTaskStatus.PENDING,
        "Queueing": MediaTaskStatus.PENDING,
        "Processing": MediaTaskStatus.RUNNING,
        "Success": MediaTaskStatus.SUCCEEDED,
        "Fail": MediaTaskStatus.FAILED,
    }

    def __init__(
        self,
        transport: MiniMaxMediaTransport,
        *,
        model: str = "MiniMax-Hailuo-2.3",
        request_timeout: float = 30.0,
        download_timeout: float = 120.0,
        max_video_bytes: int = DEFAULT_MAX_VIDEO_BYTES,
    ) -> None:
        self.transport = transport
        self.model = model
        self.request_timeout = request_timeout
        self.download_timeout = download_timeout
        self.max_video_bytes = max_video_bytes

    def submit(self, request: VideoGenerationRequest) -> VideoTask:
        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": request.prompt,
            "duration": request.duration,
            "resolution": request.resolution,
            "aigc_watermark": False,
        }
        if request.first_frame_image is not None:
            payload["first_frame_image"] = request.first_frame_image
        raw = self.transport.request_json(
            "POST",
            "/v1/video_generation",
            payload=payload,
            params=None,
            timeout=self.request_timeout,
        )
        _validate_base_response(raw)
        task_id = raw.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise MiniMaxMediaProtocolError("MiniMax submit response has no task_id")
        return VideoTask(
            provider="minimax-hailuo",
            task_id=task_id,
            status=MediaTaskStatus.PENDING,
        )

    def get_status(self, task_id: str) -> VideoTask:
        if not task_id.strip():
            raise ValueError("task_id must not be empty")
        raw = self.transport.request_json(
            "GET",
            "/v1/query/video_generation",
            payload=None,
            params={"task_id": task_id},
            timeout=self.request_timeout,
        )
        _validate_base_response(raw)
        if raw.get("task_id") != task_id:
            raise MiniMaxMediaProtocolError("MiniMax task response ID does not match")
        remote_status = raw.get("status")
        status = self.REMOTE_STATUSES.get(remote_status)
        if status is None:
            raise MiniMaxMediaProtocolError(
                f"MiniMax returned unknown video status {remote_status!r}"
            )
        error = None
        if status is MediaTaskStatus.FAILED:
            value = raw.get("error_message")
            error = value[:2000] if isinstance(value, str) and value else "video generation failed"
        file_id = raw.get("file_id")
        if isinstance(file_id, int) and file_id >= 0:
            file_id = str(file_id)
        width = raw.get("video_width")
        height = raw.get("video_height")
        if isinstance(width, int) and width <= 0:
            width = None
        if isinstance(height, int) and height <= 0:
            height = None
        try:
            return VideoTask(
                provider="minimax-hailuo",
                task_id=task_id,
                status=status,
                file_id=(
                    file_id
                    if status is MediaTaskStatus.SUCCEEDED
                    else None
                ),
                error=error,
                width=width,
                height=height,
            )
        except ValidationError as exc:
            raise MiniMaxMediaProtocolError(
                "MiniMax video task payload is invalid"
            ) from exc

    def get_result(self, task_id: str) -> VideoResult:
        task = self.get_status(task_id)
        if task.status is not MediaTaskStatus.SUCCEEDED or task.file_id is None:
            raise MiniMaxMediaTaskError(
                f"video task {task_id} is not successful: {task.status.value}"
            )
        raw = self.transport.request_json(
            "GET",
            "/v1/files/retrieve",
            payload=None,
            params={"file_id": task.file_id},
            timeout=self.request_timeout,
        )
        _validate_base_response(raw)
        file_data = raw.get("file")
        if not isinstance(file_data, dict):
            raise MiniMaxMediaProtocolError("MiniMax file response is invalid")
        if str(file_data.get("file_id")) != task.file_id:
            raise MiniMaxMediaProtocolError("MiniMax file response ID does not match")
        try:
            return VideoResult(
                provider="minimax-hailuo",
                model=self.model,
                task_id=task_id,
                file_id=task.file_id,
                download_url=file_data.get("download_url"),
                bytes=file_data.get("bytes"),
            )
        except ValidationError as exc:
            raise MiniMaxMediaProtocolError(
                "MiniMax video file payload is invalid"
            ) from exc

    def download(self, result: VideoResult, output_file: Path) -> Path:
        return self.transport.download(
            result.download_url,
            Path(output_file),
            timeout=self.download_timeout,
            max_bytes=self.max_video_bytes,
        )
