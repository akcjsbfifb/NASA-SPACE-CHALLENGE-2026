"""The two entry points that carry `activity` and `weights`."""

from __future__ import annotations

import json
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
from app.services.earth import similarity  # noqa: E402
from app.services.earth.similarity import EarthIndex  # noqa: E402
from app.workers import gurvich_search  # noqa: E402

CATALOG = json.loads((REPO_ROOT / "mcp" / "activities.json").read_text())
CATALOG_IDS = [preset["id"] for preset in CATALOG]


@pytest.fixture()
def server(tiny_index: EarthIndex, monkeypatch):
    written: list[dict] = []

    def fake_write(result: dict):
        written.append(result)
        return Path("/tmp/shortlist.json")

    monkeypatch.setattr(search_state, "_index", tiny_index)
    import app.api.search as search_routes

    monkeypatch.setattr(search_routes, "write_shortlist", fake_write)
    with TestClient(app) as client:
        yield client, written


def test_activities_returns_the_catalog_without_loading_the_grid(monkeypatch):
    monkeypatch.setattr(search_state, "_index", None)
    with TestClient(app) as client:
        response = client.get("/activities")
    assert response.status_code == 200
    body = response.json()
    assert [preset["id"] for preset in body["activities"]] == CATALOG_IDS
    assert search_state._index is None


def test_activity_brings_weights_and_values(server):
    client, _written = server
    response = client.get("/search?activity=floor_sample")
    assert response.status_code == 200
    body = response.json()
    assert "rock" not in body["variables"]
    assert body["weights"]["slope"] == 0.3
    assert body["weights"]["roughness"] == 1.0
    assert body["weights"]["rock"] is None
    assert body["activity"] == {"id": "floor_sample"}
    assert body["target"]["slope"] == 3.0


def test_preset_values_reach_the_search(server):
    client, _written = server
    response = client.get("/search?activity=polar_ice")
    assert response.status_code == 200
    body = response.json()
    assert body["variables"] == ["temperature", "ice"]
    assert body["target"]["temperature"] == -140.0
    assert body["target"]["ice"] == 1.0


def test_explicit_target_overrides_only_its_key(server):
    client, _written = server
    response = client.get("/search?activity=hadley_rille&slope=5")
    assert response.status_code == 200
    body = response.json()
    assert body["target"]["slope"] == 5.0
    assert body["target"]["roughness"] == 12.0
    assert body["weights"]["slope"] == 1.0


def test_zero_weight_drops_the_variable(server):
    client, _written = server
    response = client.get("/search?activity=polar_ice&w_temperature=0")
    assert response.status_code == 200
    body = response.json()
    assert body["variables"] == ["ice"]
    assert body["weights"]["temperature"] == 0.0
    for point in body["points"]:
        assert "temperature" not in point["scores"]


def test_search_without_activity_or_weights_still_works(server):
    client, _written = server
    response = client.get("/search?slope=8&precision=0.5")
    assert response.status_code == 200
    body = response.json()
    assert body["variables"] == ["slope"]
    assert body["weights"] == {
        "slope": 1.0,
        "roughness": None,
        "temperature": None,
        "ice": None,
        "rock": None,
    }
    assert body["activity"] is None
    assert body["points"]
    for point in body["points"]:
        assert point["grade"] in {"A", "B", "C", "D", "F"}
        assert set(point["grades"]) == set(point["scores"])


def test_unknown_activity_is_400_and_writes_no_shortlist(server):
    client, written = server
    response = client.get("/search?activity=no_such")
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "unknown_activity"
    assert body["message"]
    assert written == []


def test_weight_out_of_range_is_400(server):
    client, written = server
    response = client.get("/search?w_slope=1.5")
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "bad_weight"
    assert written == []


def test_unknown_weight_key_is_400(server):
    client, written = server
    response = client.get("/search?w_banana=1")
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "bad_weight"
    assert written == []


def test_weights_that_drop_everything_are_no_measurement(server):
    client, written = server
    response = client.get("/search?activity=landing_site&w_slope=0&w_roughness=0")
    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "no_measurement"
    assert body["message"] == "falta al menos una medición"
    assert written == []


def test_search_writes_the_shortlist_when_it_succeeds(server):
    client, written = server
    response = client.get("/search?activity=rover_wheels")
    assert response.status_code == 200
    assert len(written) == 1
    assert written[0]["activity"] == {"id": "rover_wheels"}


def _run_worker(payload: dict, index: EarthIndex, monkeypatch) -> dict:
    monkeypatch.setattr(gurvich_search, "_try_remote_search", lambda _payload: None)
    monkeypatch.setattr(gurvich_search, "_write_shortlist", lambda result: result)
    monkeypatch.setattr(gurvich_search, "_index", index)
    monkeypatch.setenv("GURVICH_NOTIFY_URL", "")
    return gurvich_search._handle_line(json.dumps(payload))


def test_worker_resolves_activity_locally(tiny_index: EarthIndex, monkeypatch):
    body = _run_worker({"activity": "polar_ice"}, tiny_index, monkeypatch)
    assert "error" not in body
    assert body["activity"] == {"id": "polar_ice"}
    assert body["weights"]["temperature"] == 1.0
    assert body["variables"] == ["temperature", "ice"]


def test_worker_reports_unknown_activity(tiny_index: EarthIndex, monkeypatch):
    body = _run_worker({"activity": "no_such"}, tiny_index, monkeypatch)
    assert body["error"] == "unknown_activity"
    assert body["message"]


def test_worker_does_not_leak_weights_into_targets(tiny_index: EarthIndex, monkeypatch):
    body = _run_worker({"weights": {"slope": 0.3}, "slope": 8}, tiny_index, monkeypatch)
    assert "error" not in body
    assert body["variables"] == ["slope"]
    assert body["weights"]["slope"] == 0.3


def test_worker_rejects_unknown_weight_key(tiny_index: EarthIndex, monkeypatch):
    body = _run_worker({"weights": {"banana": 1}}, tiny_index, monkeypatch)
    assert body["error"] == "bad_weight"


def test_worker_empty_payload_keeps_the_old_error(tiny_index: EarthIndex, monkeypatch):
    body = _run_worker({}, tiny_index, monkeypatch)
    assert body == {"error": "falta al menos una medición"}