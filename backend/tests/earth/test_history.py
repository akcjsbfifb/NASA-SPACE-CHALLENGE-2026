"""POST/GET /history: persist chosen analogs with nearest cell."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.main import app  # noqa: E402
from app.services import search_state  # noqa: E402
from app.services.earth.similarity import EarthIndex  # noqa: E402


@pytest.fixture()
def history_client(tiny_index: EarthIndex, tmp_path, monkeypatch):
    history_file = tmp_path / "history.json"
    monkeypatch.setattr(search_state, "_index", tiny_index)
    import app.api.search as search_routes

    monkeypatch.setattr(search_routes, "history_path", lambda: history_file)
    with TestClient(app) as client:
        yield client, history_file, tiny_index


def _sample_body(lat: float = 45.0, lon: float = -120.0) -> dict:
    return {
        "point": {
            "lat": lat,
            "lon": lon,
            "closeness": 0.91,
            "rock": "vb",
            "scores": {"slope": 0.88, "roughness": 0.75},
            "grade": "high",
        },
        "query": {
            "target": {"slope": 8.0, "roughness": 25.0},
            "weights": {"slope": 1.0, "roughness": 1.0},
            "precision": 0.75,
            "temperature_mode": "absolute",
            "min_closeness": 0.5,
            "activity": {"id": "landing_site"},
        },
    }


def test_post_persists_cell_and_get_returns_it(history_client):
    client, history_file, _index = history_client
    response = client.post("/history", json=_sample_body())
    assert response.status_code == 200
    entry = response.json()
    assert entry["point"]["lat"] == 45.0
    assert entry["point"]["lon"] == -120.0
    assert "id" in entry and "at" in entry
    cell = entry["cell"]
    assert cell["slope_deg"] == pytest.approx(5.0)
    assert cell["roughness_m"] == pytest.approx(20.0)
    assert cell["rock"] == "vb"
    assert history_file.exists()

    listed = client.get("/history")
    assert listed.status_code == 200
    entries = listed.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["id"] == entry["id"]
    assert entries[0]["cell"]["slope_deg"] == cell["slope_deg"]


def test_invalid_body_returns_400(history_client):
    client, history_file, _index = history_client
    bad = client.post("/history", json={"point": {"lat": "x", "lon": -120}, "query": {}})
    missing = client.post("/history", json={"point": {"lon": 1}})
    assert bad.status_code == 400
    assert missing.status_code == 400
    assert not history_file.exists()


def test_no_land_returns_404_and_does_not_append(history_client, monkeypatch):
    client, history_file, index = history_client
    monkeypatch.setattr(index, "nearest", lambda _lat, _lon: None)
    response = client.post("/history", json=_sample_body())
    assert response.status_code == 404
    assert response.json()["error"] == "no land cell"
    assert not history_file.exists()


def test_fifty_first_cap_drops_oldest(history_client):
    client, _history_file, _index = history_client
    first_id = None
    for ordinal in range(51):
        body = _sample_body()
        body["point"]["closeness"] = 0.5 + ordinal * 0.001
        posted = client.post("/history", json=body)
        assert posted.status_code == 200
        if ordinal == 0:
            first_id = posted.json()["id"]
        elif ordinal == 50:
            newest_id = posted.json()["id"]

    listed = client.get("/history").json()["entries"]
    assert len(listed) == 50
    ids = [item["id"] for item in listed]
    assert first_id not in ids
    assert ids[0] == newest_id