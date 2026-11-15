"""The two entry points that carry `activity` and `weights`.

`GET /search` and `GET /activities` run against the real handler on the tiny
grid. The worker is exercised in process: only its local path matters here, and
the subprocess harness already lives in `test_gurvich_search.py`.
"""

from __future__ import annotations

import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "backend" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import gurvich_search  # noqa: E402
import serve_search  # noqa: E402
from similarity import EarthIndex  # noqa: E402

CATALOG = json.loads((REPO_ROOT / "mcp" / "activities.json").read_text())
CATALOG_IDS = [preset["id"] for preset in CATALOG]


def _get(base: str, path: str) -> tuple[int, dict]:
    try:
        with urlopen(f"{base}{path}", timeout=10) as response:
            return response.getcode(), json.loads(response.read().decode())
    except HTTPError as error:
        return error.code, json.loads(error.read().decode())


@pytest.fixture()
def server(tiny_index: EarthIndex, monkeypatch):
    written: list[dict] = []
    monkeypatch.setattr(serve_search, "_index", tiny_index)
    monkeypatch.setattr(serve_search, "write_shortlist", written.append)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), serve_search.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", written
    finally:
        httpd.shutdown()
        httpd.server_close()


# GET /activities


def test_activities_returns_the_catalog_without_loading_the_grid(monkeypatch):
    monkeypatch.setattr(serve_search, "_index", None)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), serve_search.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _get(f"http://127.0.0.1:{httpd.server_address[1]}", "/activities")
    finally:
        httpd.shutdown()
        httpd.server_close()

    assert status == 200
    assert [preset["id"] for preset in body["activities"]] == CATALOG_IDS
    assert serve_search._index is None


# GET /search


def test_activity_brings_weights_and_values(server):
    base, _written = server
    status, body = _get(base, "/search?activity=floor_sample")

    assert status == 200
    assert "rock" not in body["variables"]
    assert body["weights"]["slope"] == 0.3
    assert body["weights"]["roughness"] == 1.0
    assert body["weights"]["rock"] is None
    assert body["activity"] == {"id": "floor_sample"}
    assert body["target"]["slope"] == 3.0


def test_preset_values_reach_the_search(server):
    base, _written = server
    status, body = _get(base, "/search?activity=polar_ice")

    assert status == 200
    assert body["variables"] == ["temperature", "ice"]
    assert body["target"]["temperature"] == -140.0
    assert body["target"]["ice"] == 1.0


def test_explicit_target_overrides_only_its_key(server):
    base, _written = server
    status, body = _get(base, "/search?activity=hadley_rille&slope=5")

    assert status == 200
    assert body["target"]["slope"] == 5.0
    assert body["target"]["roughness"] == 12.0
    assert body["weights"]["slope"] == 1.0


def test_zero_weight_drops_the_variable(server):
    base, _written = server
    status, body = _get(base, "/search?activity=polar_ice&w_temperature=0")

    assert status == 200
    assert body["variables"] == ["ice"]
    assert body["weights"]["temperature"] == 0.0
    for point in body["points"]:
        assert "temperature" not in point["scores"]


def test_search_without_activity_or_weights_still_works(server):
    base, _written = server
    status, body = _get(base, "/search?slope=8&precision=0.5")

    assert status == 200
    assert body["variables"] == ["slope"]
    assert body["weights"] == {
        "slope": 1.0,
        "roughness": None,
        "temperature": None,
        "ice": None,
        "rock": None,
    }
    assert body["activity"] is None
    assert body["points"], "the tiny grid must return at least one point"
    for point in body["points"]:
        assert point["grade"] in {"A", "B", "C", "D", "F"}
        assert set(point["grades"]) == set(point["scores"])


def test_unknown_activity_is_400_and_writes_no_shortlist(server):
    base, written = server
    status, body = _get(base, "/search?activity=no_such")

    assert status == 400
    assert body["error"] == "unknown_activity"
    assert body["message"]
    assert written == []


def test_weight_out_of_range_is_400(server):
    base, written = server
    status, body = _get(base, "/search?w_slope=1.5")

    assert status == 400
    assert body["error"] == "bad_weight"
    assert written == []


def test_unknown_weight_key_is_400(server):
    base, written = server
    status, body = _get(base, "/search?w_banana=1")

    assert status == 400
    assert body["error"] == "bad_weight"
    assert written == []


def test_weights_that_drop_everything_are_no_measurement(server):
    base, written = server
    status, body = _get(base, "/search?activity=landing_site&w_slope=0&w_roughness=0")

    assert status == 400
    assert body["error"] == "no_measurement"
    assert body["message"] == "falta al menos una medición"
    assert written == []


def test_search_writes_the_shortlist_when_it_succeeds(server):
    base, written = server
    status, _body = _get(base, "/search?activity=rover_wheels")

    assert status == 200
    assert len(written) == 1
    assert written[0]["activity"] == {"id": "rover_wheels"}


# Worker, local path only.


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
