"""Persistent EarthIndex worker: one JSON line on stdin, one JSON line on stdout."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = ROOT / "backend" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import similarity
from similarity import EarthIndex, write_shortlist

_FLOAT_KEYS = ("slope", "roughness", "tmin", "ice")
NOTIFY_TOKEN_HEADER = "X-Gurvich-Notify-Token"
DEFAULT_NOTIFY_TOKEN_PATH = Path("/tmp/gurvich-notify.token")

_index: EarthIndex | None = None


def _columns_dir() -> Path:
    env = os.environ.get("GURVICH_COLUMNS_DIR")
    if env:
        return Path(env)
    return similarity.COLUMNS_DIR


def _shortlist_path() -> Path:
    env = os.environ.get("GURVICH_SHORTLIST")
    if env:
        return Path(env)
    return similarity.SHORTLIST


def _search_base_url() -> str:
    raw = os.environ.get("GURVICH_SEARCH_BASE", "http://127.0.0.1:8787").strip()
    return raw.rstrip("/")


def _search_kwargs(payload: dict) -> dict:
    kwargs: dict = {}
    for key in _FLOAT_KEYS:
        if key not in payload or payload[key] is None:
            continue
        kwargs[key] = float(payload[key])
    rock = payload.get("rock")
    if rock is not None:
        kwargs["rock"] = str(rock)
    precision = payload.get("precision")
    kwargs["precision"] = 0.7 if precision is None else float(precision)
    return kwargs


def _search_query_params(payload: dict) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = []
    for key in _FLOAT_KEYS:
        if key not in payload or payload[key] is None:
            continue
        params.append((key, str(payload[key])))
    rock = payload.get("rock")
    if rock is not None and str(rock) != "":
        params.append(("rock", str(rock)))
    precision = payload.get("precision")
    if precision is None:
        params.append(("precision", "0.7"))
    else:
        params.append(("precision", str(precision)))
    return params


def _notify_url() -> str | None:
    if "GURVICH_NOTIFY_URL" in os.environ:
        raw = os.environ["GURVICH_NOTIFY_URL"].strip()
        return raw or None
    return f"{_search_base_url()}/notify"


def _notify_token() -> str | None:
    path = Path(os.environ.get("GURVICH_NOTIFY_TOKEN_PATH", str(DEFAULT_NOTIFY_TOKEN_PATH)))
    if not path.is_file():
        return None
    token = path.read_text().strip()
    return token or None


def _try_remote_search(payload: dict) -> dict | None:
    query = urlencode(_search_query_params(payload))
    url = f"{_search_base_url()}/search?{query}"
    try:
        request = Request(url, method="GET")
        with urlopen(request, timeout=2) as response:
            if response.getcode() != 200:
                return None
            body = json.loads(response.read().decode())
    except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(body, dict):
        return None
    if "error" in body:
        return body
    return body


def _notify_frontend(result: dict) -> dict:
    url = _notify_url()
    if not url:
        return result
    headers = {"Content-Type": "application/json"}
    token = _notify_token()
    if token:
        headers[NOTIFY_TOKEN_HEADER] = token
    try:
        payload = json.dumps(result, ensure_ascii=False).encode()
        request = Request(url, data=payload, headers=headers, method="POST")
        with urlopen(request, timeout=2) as response:
            response.read()
    except (OSError, URLError, TimeoutError, ValueError) as error:
        return {**result, "frontend_error": str(error)}
    return result


def _write_shortlist(result: dict) -> dict:
    dest = _shortlist_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    previous = similarity.SHORTLIST
    similarity.SHORTLIST = dest
    try:
        write_shortlist(result)
    except OSError as error:
        result = {**result, "shortlist_error": str(error)}
    finally:
        similarity.SHORTLIST = previous
    return result


def _lazy_index() -> EarthIndex:
    global _index
    if _index is None:
        _index = EarthIndex(columns_dir=_columns_dir())
    return _index


def _handle_line(line: str) -> dict:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as error:
        return {"error": f"invalid json: {error}"}
    if not isinstance(payload, dict):
        return {"error": "request must be a JSON object"}

    remote = _try_remote_search(payload)
    if remote is not None:
        return remote

    try:
        result = _lazy_index().search(**_search_kwargs(payload))
    except (FileNotFoundError, ValueError) as error:
        return {"error": str(error)}
    return _notify_frontend(_write_shortlist(result))


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        response = _handle_line(line)
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())