from __future__ import annotations

import json
import time
from enum import Enum
from typing import Any, Callable, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from storymotion.adapters import adapt_penshot_result, screenplay_to_penshot_text
from storymotion.models import ScreenplayPackage, ShotPackage


class SidecarError(RuntimeError):
    """Base class for expected PenShot sidecar failures."""


class SidecarUnavailableError(SidecarError):
    """The sidecar could not be reached or returned a transport error."""


class SidecarProtocolError(SidecarError):
    """The sidecar response did not satisfy the StoryMotion contract."""


class SidecarTaskError(SidecarError):
    """The sidecar accepted a task but could not complete it."""


class SidecarTimeoutError(SidecarError):
    """The sidecar task exceeded StoryMotion's overall deadline."""


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SubmitStoryboardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script: str = Field(min_length=1, max_length=200_000)
    project_id: str | None = Field(default=None, min_length=1, max_length=200)
    language: str = Field(default="zh", pattern="^(zh|en)$")
    style: str | None = Field(default=None, min_length=1, max_length=100)


class SubmitStoryboardResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_id: str = Field(min_length=1, max_length=200)


class TaskResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_id: str = Field(min_length=1, max_length=200)
    status: TaskStatus
    result: dict[str, Any] | None = None
    error: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_terminal_payload(self) -> "TaskResponse":
        if self.status is TaskStatus.COMPLETED and self.result is None:
            raise ValueError("completed task must include result")
        return self


class JsonTransport(Protocol):
    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None,
        timeout: float,
    ) -> dict[str, Any]: ...


class UrllibJsonTransport:
    """Small JSON transport used to keep PenShot dependencies out of StoryMotion."""

    def __init__(self, base_url: str) -> None:
        normalized = base_url.rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("base_url must use http or https")
        self.base_url = normalized

    def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None,
        timeout: float,
    ) -> dict[str, Any]:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(2_000_001)
        except HTTPError as exc:
            detail = exc.read(2_001).decode("utf-8", errors="replace")
            raise SidecarUnavailableError(
                f"sidecar HTTP {exc.code}: {detail[:2000]}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise SidecarUnavailableError(f"sidecar unavailable: {exc}") from exc

        if len(raw) > 2_000_000:
            raise SidecarProtocolError("sidecar response exceeds 2 MB")
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SidecarProtocolError("sidecar returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise SidecarProtocolError("sidecar JSON response must be an object")
        return decoded


class PenShotSidecarClient:
    def __init__(
        self,
        transport: JsonTransport,
        *,
        poll_interval: float = 0.5,
        overall_timeout: float = 300.0,
        request_timeout: float = 10.0,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if poll_interval <= 0 or overall_timeout <= 0 or request_timeout <= 0:
            raise ValueError("sidecar timeouts and poll interval must be positive")
        self.transport = transport
        self.poll_interval = float(poll_interval)
        self.overall_timeout = float(overall_timeout)
        self.request_timeout = float(request_timeout)
        self._sleep = sleep
        self._monotonic = monotonic

    def breakdown_screenplay(
        self,
        screenplay: ScreenplayPackage,
        *,
        project_id: str | None = None,
        language: str = "zh",
        style: str | None = None,
    ) -> dict[str, Any]:
        request_model = SubmitStoryboardRequest(
            script=screenplay_to_penshot_text(screenplay),
            project_id=project_id,
            language=language,
            style=style,
        )
        started = self._monotonic()
        deadline = started + self.overall_timeout
        submit_raw = self.transport.request_json(
            "POST",
            "/v1/storyboards",
            payload=request_model.model_dump(exclude_none=True),
            timeout=min(self.request_timeout, self.overall_timeout),
        )
        submit = self._validate(SubmitStoryboardResponse, submit_raw, "submit")
        task_path = f"/v1/tasks/{quote(submit.task_id, safe='')}"

        while True:
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                self._cancel(task_path)
                raise SidecarTimeoutError(
                    f"sidecar task {submit.task_id} exceeded "
                    f"{self.overall_timeout:g}s"
                )
            status_raw = self.transport.request_json(
                "GET",
                task_path,
                payload=None,
                timeout=min(self.request_timeout, remaining),
            )
            task = self._validate(TaskResponse, status_raw, "task")
            if task.task_id != submit.task_id:
                raise SidecarProtocolError("task response ID does not match submission")
            if task.status is TaskStatus.COMPLETED:
                assert task.result is not None
                return task.result
            if task.status in (TaskStatus.FAILED, TaskStatus.CANCELLED):
                detail = task.error or task.status.value
                raise SidecarTaskError(
                    f"sidecar task {task.task_id} {task.status.value}: {detail}"
                )

            remaining = deadline - self._monotonic()
            if remaining <= 0:
                continue
            self._sleep(min(self.poll_interval, remaining))

    def _cancel(self, task_path: str) -> None:
        try:
            self.transport.request_json(
                "DELETE",
                task_path,
                payload=None,
                timeout=min(self.request_timeout, 2.0),
            )
        except SidecarError:
            pass

    @staticmethod
    def _validate(model_type, raw: dict[str, Any], label: str):
        try:
            return model_type.model_validate(raw)
        except ValidationError as exc:
            raise SidecarProtocolError(
                f"invalid sidecar {label} response: {exc.errors(include_url=False)}"
            ) from exc


class PenShotSidecarProvider:
    def __init__(
        self,
        client: PenShotSidecarClient,
        *,
        project_id: str | None = None,
        language: str = "zh",
        style: str | None = None,
    ) -> None:
        self.client = client
        self.project_id = project_id
        self.language = language
        self.style = style

    def generate(self, screenplay: ScreenplayPackage) -> ShotPackage:
        raw_result = self.client.breakdown_screenplay(
            screenplay,
            project_id=self.project_id,
            language=self.language,
            style=self.style,
        )
        try:
            return adapt_penshot_result(raw_result, screenplay)
        except ValueError as exc:
            raise SidecarProtocolError(
                f"invalid PenShot storyboard result: {exc}"
            ) from exc


class ShotProvider(Protocol):
    def generate(self, screenplay: ScreenplayPackage) -> ShotPackage: ...


class FallbackShotProvider:
    def __init__(
        self,
        primary: ShotProvider,
        fallback: ShotProvider,
        *,
        fallback_on: tuple[type[Exception], ...] = (SidecarError,),
    ) -> None:
        if not fallback_on:
            raise ValueError("fallback_on must contain at least one exception type")
        if not all(
            isinstance(error_type, type) and issubclass(error_type, Exception)
            for error_type in fallback_on
        ):
            raise TypeError("fallback_on entries must be Exception types")
        self.primary = primary
        self.fallback = fallback
        self.fallback_on = fallback_on

    def generate(self, screenplay: ScreenplayPackage) -> ShotPackage:
        try:
            return self.primary.generate(screenplay)
        except self.fallback_on:
            return self.fallback.generate(screenplay)
