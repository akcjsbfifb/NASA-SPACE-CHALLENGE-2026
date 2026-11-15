"""SSE /notify on serve_search.Handler without loading EarthIndex."""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend" / "scripts"))

import serve_search  # noqa: E402
from serve_search import (  # noqa: E402
    Handler,
    MAX_NOTIFY_BODY,
    _sse_clients,
    _sse_lock,
    init_notify_token,
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _read_sse_data(connection: HTTPConnection, deadline: float) -> dict:
    while time.monotonic() < deadline:
        response = connection.getresponse()
        assert response.status == 200
        assert response.getheader("Content-Type", "").startswith("text/event-stream")
        while time.monotonic() < deadline:
            line = response.fp.readline()
            if not line:
                break
            text = line.decode().rstrip("\r\n")
            if text.startswith("data: "):
                return json.loads(text[6:])
            if text == "":
                continue
    raise AssertionError("no SSE data before deadline")


def _wait_no_sse_data(connection: HTTPConnection, deadline: float) -> None:
    response = connection.getresponse()
    assert response.status == 200
    while time.monotonic() < deadline:
        line = response.fp.readline()
        if not line:
            time.sleep(0.05)
            continue
        text = line.decode().rstrip("\r\n")
        if text.startswith("data: "):
            raise AssertionError("unexpected SSE data")


def _notify_headers() -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Gurvich-Notify-Token": serve_search.NOTIFY_TOKEN,
    }


@pytest.fixture()
def notify_server():
    init_notify_token()
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        with _sse_lock:
            _sse_clients.clear()


def test_notify_reaches_sse_client(notify_server):
    port = notify_server
    body = {"returned": 1, "points": [{"lat": 0.0, "lon": 0.0, "closeness": 0.9}]}
    events = HTTPConnection("127.0.0.1", port, timeout=5)
    events.request("GET", "/events")
    received: dict = {}
    error: list[BaseException] = []

    def reader() -> None:
        try:
            received["body"] = _read_sse_data(events, time.monotonic() + 5.0)
        except BaseException as exc:  # pragma: no cover
            error.append(exc)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    time.sleep(0.2)

    post = HTTPConnection("127.0.0.1", port, timeout=5)
    post.request(
        "POST",
        "/notify",
        body=json.dumps(body).encode(),
        headers=_notify_headers(),
    )
    notify_response = post.getresponse()
    notify_payload = json.loads(notify_response.read().decode())
    assert notify_response.status == 200
    assert notify_payload["listeners"] >= 1

    thread.join(timeout=5)
    assert not error, error
    assert received["body"] == body
    events.close()


def test_notify_without_token_returns_401_and_no_sse(notify_server):
    port = notify_server
    body = {"returned": 1, "points": [{"lat": 1.0, "lon": 2.0, "closeness": 0.5}]}
    events = HTTPConnection("127.0.0.1", port, timeout=5)
    events.request("GET", "/events")
    sse_error: list[BaseException] = []

    def reader() -> None:
        try:
            _wait_no_sse_data(events, time.monotonic() + 2.5)
        except BaseException as exc:  # pragma: no cover
            sse_error.append(exc)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    time.sleep(0.2)

    post = HTTPConnection("127.0.0.1", port, timeout=5)
    post.request(
        "POST",
        "/notify",
        body=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    response = post.getresponse()
    payload = json.loads(response.read().decode())
    assert response.status == 401
    assert payload["error"] == "unauthorized"

    thread.join(timeout=3)
    assert not sse_error, sse_error
    events.close()


def test_notify_payload_over_limit_returns_413(notify_server):
    port = notify_server
    post = HTTPConnection("127.0.0.1", port, timeout=5)
    post.request(
        "POST",
        "/notify",
        body=b"{}",
        headers={
            **_notify_headers(),
            "Content-Length": str(MAX_NOTIFY_BODY + 1),
        },
    )
    response = post.getresponse()
    payload = json.loads(response.read().decode())
    assert response.status == 413
    assert payload["error"] == "payload too large"


def test_notify_without_listeners(notify_server):
    port = notify_server
    post = HTTPConnection("127.0.0.1", port, timeout=5)
    post.request(
        "POST",
        "/notify",
        body=json.dumps({"returned": 0, "points": []}).encode(),
        headers=_notify_headers(),
    )
    response = post.getresponse()
    payload = json.loads(response.read().decode())
    assert response.status == 200
    assert payload["listeners"] == 0