"""Persistent EarthIndex worker: one JSON line on stdin, one JSON line on stdout."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import get_settings
from app.services.earth import similarity
from app.services.earth.activities import VARIABLES, ActivityError, resolve
from app.services.earth.similarity import EarthIndex, parse_criteria, write_shortlist

CONTROL_KEYS = ("precision", "min_worst", "activity", "weights")
NOTIFY_TOKEN_HEADER = "X-Artemis-Notify-Token"

_index: EarthIndex | None = None


def _columns_dir() -> Path:
    env = os.environ.get("ARTEMIS_COLUMNS_DIR")
    if env:
        return Path(env)
    return similarity.COLUMNS_DIR


def _shortlist_path() -> Path:
    env = os.environ.get("ARTEMIS_SHORTLIST")
    if env:
        return Path(env)
    return similarity.SHORTLIST


def _search_base_url() -> str:
    raw = os.environ.get("ARTEMIS_SEARCH_BASE")
    if raw:
        return raw.strip().rstrip("/")
    return get_settings().server.search_base.rstrip("/")


def _targets(payload: dict) -> dict[str, str]:
    return {
        key: str(value)
        for key, value in payload.items()
        if key not in CONTROL_KEYS and value is not None and value != ""
    }


def _search_query_params(payload: dict) -> list[tuple[str, str]]:
    params = list(_targets(payload).items())
    activity = payload.get("activity")
    if activity is not None and activity != "":
        params.append(("activity", str(activity)))
    weights = payload.get("weights")
    if isinstance(weights, dict):
        for name in VARIABLES:
            value = weights.get(name)
            if value is not None:
                params.append((f"w_{name}", str(value)))
    precision = payload.get("precision")
    params.append(("precision", "0.7" if precision is None else str(precision)))
    if payload.get("min_worst") is not None:
        params.append(("min_worst", str(payload["min_worst"])))
    return params


def _notify_url() -> str | None:
    if "ARTEMIS_NOTIFY_URL" in os.environ:
        raw = os.environ["ARTEMIS_NOTIFY_URL"].strip()
        return raw or None
    return f"{_search_base_url()}/notify"


def _notify_token() -> str | None:
    path = Path(
        os.environ.get(
            "ARTEMIS_NOTIFY_TOKEN_PATH",
            str(get_settings().paths.notify_token),
        )
    )
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
        index = _lazy_index()
        targets, weights, preset = resolve(
            payload.get("activity"),
            _targets(payload),
            payload.get("weights") or {},
        )
        result = index.search(
            parse_criteria(index.contract, targets),
            precision=0.7 if payload.get("precision") is None else float(payload["precision"]),
            min_worst=None if payload.get("min_worst") is None else float(payload["min_worst"]),
            weights=weights,
            activity={"id": preset["id"]} if preset else None,
        )
    except ActivityError as error:
        return {"error": error.code, "message": error.message}
    except ValueError as error:
        if str(error) == "falta al menos una medición":
            return {"error": str(error)}
        return {"error": str(error)}
    except FileNotFoundError as error:
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