from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from storymotion.models import ScreenplayPackage
from storymotion.providers.penshot_sidecar import (
    PenShotSidecarClient,
    SidecarProtocolError,
    SidecarUnavailableError,
    UrllibJsonTransport,
)


ROOT = Path(__file__).resolve().parents[1]
SCREENPLAY_FILE = (
    ROOT / "outputs/verification/screenplay/screenplay_package_repaired.json"
)
RESULT_FILE = ROOT / "tests/fixtures/penshot_fragments.json"


class FakeSidecarHandler(BaseHTTPRequestHandler):
    calls: list[tuple[str, str, dict[str, Any] | None]] = []
    raw_result: dict[str, Any] = {}

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, status: int, payload: Any, content_type: str = "application/json") -> None:
        if isinstance(payload, bytes):
            body = payload
        else:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.calls.append(("POST", self.path, payload))
        if self.path == "/v1/storyboards":
            self._send(202, {"task_id": "loopback-task"})
        else:
            self._send(404, {"error": "not found"})

    def do_GET(self) -> None:
        self.calls.append(("GET", self.path, None))
        if self.path == "/v1/tasks/loopback-task":
            self._send(
                200,
                {
                    "task_id": "loopback-task",
                    "status": "completed",
                    "result": self.raw_result,
                },
            )
        elif self.path == "/invalid-json":
            self._send(200, b"not-json", "text/plain")
        else:
            self._send(503, {"error": "temporarily unavailable"})

    def do_DELETE(self) -> None:
        self.calls.append(("DELETE", self.path, None))
        self._send(200, {"task_id": "loopback-task", "status": "cancelled"})


@pytest.fixture
def sidecar_url() -> str:
    FakeSidecarHandler.calls = []
    FakeSidecarHandler.raw_result = json.loads(
        RESULT_FILE.read_text(encoding="utf-8")
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeSidecarHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_real_http_transport_obeys_contract(sidecar_url: str) -> None:
    screenplay = ScreenplayPackage.model_validate_json(
        SCREENPLAY_FILE.read_text(encoding="utf-8")
    )
    client = PenShotSidecarClient(
        UrllibJsonTransport(sidecar_url), overall_timeout=2
    )

    result = client.breakdown_screenplay(screenplay, project_id="中文项目")

    assert len(result["fragments"]) == 6
    assert [call[:2] for call in FakeSidecarHandler.calls] == [
        ("POST", "/v1/storyboards"),
        ("GET", "/v1/tasks/loopback-task"),
    ]
    assert FakeSidecarHandler.calls[0][2]["project_id"] == "中文项目"
    assert "scene_001" in FakeSidecarHandler.calls[0][2]["script"]


def test_real_transport_normalizes_http_error(sidecar_url: str) -> None:
    transport = UrllibJsonTransport(sidecar_url)

    with pytest.raises(SidecarUnavailableError, match="HTTP 503"):
        transport.request_json("GET", "/unavailable", payload=None, timeout=2)


def test_real_transport_rejects_invalid_json(sidecar_url: str) -> None:
    transport = UrllibJsonTransport(sidecar_url)

    with pytest.raises(SidecarProtocolError, match="invalid JSON"):
        transport.request_json("GET", "/invalid-json", payload=None, timeout=2)


def test_real_transport_sends_delete(sidecar_url: str) -> None:
    transport = UrllibJsonTransport(sidecar_url)

    response = transport.request_json(
        "DELETE", "/v1/tasks/loopback-task", payload=None, timeout=2
    )

    assert response["status"] == "cancelled"
    assert FakeSidecarHandler.calls[-1][:2] == (
        "DELETE",
        "/v1/tasks/loopback-task",
    )
