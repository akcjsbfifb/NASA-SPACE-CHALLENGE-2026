"""SSE /notify on the FastAPI app without loading EarthIndex."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.main import app  # noqa: E402
from app.services import notify  # noqa: E402


@pytest.fixture()
def notify_client():
    notify.init_notify_token()
    with TestClient(app) as client:
        yield client
    with notify._sse_lock:
        notify._sse_clients.clear()


def test_notify_reaches_sse_client(notify_client):
    body = {"returned": 1, "points": [{"lat": 0.0, "lon": 0.0, "closeness": 0.9}]}
    queue = notify.register_sse_client()
    try:
        response = notify_client.post(
            "/notify",
            content=json.dumps(body),
            headers={
                "Content-Type": "application/json",
                "X-Artemis-Notify-Token": notify.NOTIFY_TOKEN,
            },
        )
        assert response.status_code == 200
        assert response.json()["listeners"] >= 1
        line = queue.get(timeout=2.0)
        assert json.loads(line.removeprefix("data: ").strip()) == body
    finally:
        notify.unregister_sse_client(queue)


def test_notify_without_token_returns_401_and_no_sse(notify_client):
    body = {"returned": 1, "points": [{"lat": 1.0, "lon": 2.0, "closeness": 0.5}]}
    response = notify_client.post(
        "/notify",
        content=json.dumps(body),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401
    assert response.json()["error"] == "unauthorized"


def test_notify_payload_over_limit_returns_413(notify_client):
    response = notify_client.post(
        "/notify",
        content=b"{}",
        headers={
            "Content-Type": "application/json",
            "X-Artemis-Notify-Token": notify.NOTIFY_TOKEN,
            "Content-Length": str(notify.MAX_NOTIFY_BODY + 1),
        },
    )
    assert response.status_code == 413
    assert response.json()["error"] == "payload too large"


def test_notify_without_listeners(notify_client):
    response = notify_client.post(
        "/notify",
        content=json.dumps({"returned": 0, "points": []}),
        headers={
            "Content-Type": "application/json",
            "X-Artemis-Notify-Token": notify.NOTIFY_TOKEN,
        },
    )
    assert response.status_code == 200
    assert response.json()["listeners"] == 0