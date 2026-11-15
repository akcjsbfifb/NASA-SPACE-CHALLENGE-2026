"""artemis_search worker: stdin protocol, single EarthIndex, temp shortlist."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TESTS = REPO_ROOT / "backend" / "tests" / "earth"
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(TESTS))

from app.cli.extract_earth_columns import extract  # noqa: E402
from test_earth_columns_mmap import _synthetic_parquet  # noqa: E402

WORKER = BACKEND / "app" / "workers" / "artemis_search.py"
PYTHON = Path(sys.executable)


@pytest.fixture()
def tiny_columns(tmp_path):
    parquet_path = tmp_path / "tiny.parquet"
    columns_dir = tmp_path / "columns"
    _synthetic_parquet(parquet_path)
    extract(parquet_path, columns_dir)
    return columns_dir


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _FakeSearchHandler(BaseHTTPRequestHandler):
    hits = 0

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/search":
            self.send_response(404)
            self.end_headers()
            return
        _FakeSearchHandler.hits += 1
        query = parse_qs(parsed.query)
        body = {
            "returned": 1,
            "precision": float(query.get("precision", ["0.7"])[0]),
            "points": [{"lat": 10.0, "lon": 20.0, "closeness": 0.88}],
            "target": {"slope_deg": float(query.get("slope", ["5"])[0])},
        }
        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:
        return None


@pytest.fixture()
def fake_search_server():
    _FakeSearchHandler.hits = 0
    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), _FakeSearchHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_worker_imports_app_when_launched_from_repo_root():
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    script = json.dumps(str(WORKER))
    result = subprocess.run(
        [str(PYTHON), "-c", f"import runpy; runpy.run_path({script}, run_name='probe')"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


def _run_worker(columns_dir: Path, shortlist_path: Path, extra_env: dict | None = None):
    env = {
        **__import__("os").environ,
        "ARTEMIS_COLUMNS_DIR": str(columns_dir),
        "ARTEMIS_SHORTLIST": str(shortlist_path),
        "ARTEMIS_NOTIFY_URL": "",
        "ARTEMIS_SEARCH_BASE": "http://127.0.0.1:9",
    }
    if extra_env:
        env.update(extra_env)
    env["PYTHONPATH"] = str(BACKEND)
    return subprocess.Popen(
        [str(PYTHON), str(WORKER)],
        cwd=REPO_ROOT,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _exchange(proc: subprocess.Popen, payload: dict) -> dict:
    assert proc.stdin is not None
    assert proc.stdout is not None
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    assert line
    return json.loads(line)


def test_worker_two_searches_one_process(tiny_columns, tmp_path):
    shortlist = tmp_path / "shortlist.json"
    proc = _run_worker(tiny_columns, shortlist)
    try:
        first = _exchange(proc, {"slope": 8.0, "rock": "vb", "precision": 0.5})
        assert first.get("error") is None
        assert first["returned"] >= 1
        assert shortlist.is_file()

        second = _exchange(proc, {"roughness": 25.0, "precision": 0.6})
        assert second.get("error") is None
        assert second["returned"] >= 1
        data = json.loads(shortlist.read_text())
        # Shortlist target uses contract ids, not column names.
        assert data["target"]["roughness"] == 25.0
        assert data["variables"] == ["roughness"]
    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)


def test_worker_search_error_stays_alive(tiny_columns, tmp_path):
    shortlist = tmp_path / "shortlist.json"
    proc = _run_worker(tiny_columns, shortlist)
    try:
        bad = _exchange(proc, {"precision": 0.7})
        assert bad == {"error": "falta al menos una medición"}

        ok = _exchange(proc, {"slope": 5.0, "precision": 0.5})
        assert ok.get("error") is None
    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)


def test_worker_unknown_rock(tiny_columns, tmp_path):
    proc = _run_worker(tiny_columns, tmp_path / "shortlist.json")
    try:
        body = _exchange(proc, {"slope": 1.0, "rock": "nope", "precision": 0.5})
        assert body["error"].startswith("unknown rock")
    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)


def test_worker_missing_columns_on_local_search(tmp_path):
    missing = tmp_path / "no_columns"
    proc = _run_worker(
        missing,
        tmp_path / "shortlist.json",
        {"ARTEMIS_SEARCH_BASE": "http://127.0.0.1:9"},
    )
    try:
        body = _exchange(proc, {"slope": 5.0, "precision": 0.5})
        assert "error" in body
        assert proc.poll() is None
    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)


def test_worker_uses_remote_search_without_earth_index(fake_search_server, tmp_path):
    shortlist = tmp_path / "shortlist.json"
    base = f"http://127.0.0.1:{fake_search_server}"
    proc = _run_worker(
        tmp_path / "no_columns",
        shortlist,
        {"ARTEMIS_SEARCH_BASE": base},
    )
    try:
        body = _exchange(proc, {"slope": 5.0, "precision": 0.6})
        assert body.get("error") is None
        assert body["returned"] == 1
        assert body["points"][0]["lat"] == 10.0
        assert not shortlist.is_file()
        assert _FakeSearchHandler.hits == 1
    finally:
        proc.stdin.close()
        proc.terminate()
        proc.wait(timeout=5)
