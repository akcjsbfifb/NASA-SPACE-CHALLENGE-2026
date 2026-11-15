"""Legacy HTTP 404 body and CORS contract from serve_search."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.main import app  # noqa: E402

NOT_FOUND_BODY = {"error": "not found"}


def test_unknown_path_returns_legacy_not_found_and_cors_star():
    with TestClient(app) as client:
        response = client.get("/no-such-route")
    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY
    assert response.headers.get("access-control-allow-origin") == "*"


def test_post_search_returns_legacy_not_found_not_405():
    with TestClient(app) as client:
        response = client.post("/search")
    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY
    assert "Method Not Allowed" not in response.text


def test_get_notify_returns_legacy_not_found_not_405():
    with TestClient(app) as client:
        response = client.get("/notify")
    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY
    assert response.headers.get("access-control-allow-origin") == "*"