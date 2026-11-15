"""Append-only analog choice history on disk."""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

MAX_ENTRIES = 50

POINT_FIELDS = ("closeness", "rock", "scores", "grade")


def _lock_exclusive(handle) -> None:
    """Keep writers mutually exclusive. POSIX uses flock; Windows locks the first byte with msvcrt.
    The Windows branch was not executed in this Linux session.
    """
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)


def _unlock(handle) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read_entries(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    if not raw.strip():
        return []
    data = json.loads(raw)
    if isinstance(data, dict):
        entries = data.get("entries")
        if isinstance(entries, list):
            return entries
    return []


def _write_locked(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text('{"entries": []}', encoding="utf-8")
    payload = json.dumps({"entries": entries}, ensure_ascii=False, indent=2)
    with path.open("r+", encoding="utf-8") as handle:
        _lock_exclusive(handle)
        try:
            handle.seek(0)
            handle.write(payload)
            handle.truncate()
        finally:
            _unlock(handle)


def append_entry(path: Path, entry: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text('{"entries": []}', encoding="utf-8")
    with path.open("r+", encoding="utf-8") as handle:
        _lock_exclusive(handle)
        try:
            handle.seek(0)
            raw = handle.read()
            if raw.strip():
                data = json.loads(raw)
                entries = list(data.get("entries", []))
            else:
                entries = []
            entries.insert(0, entry)
            del entries[MAX_ENTRIES:]
            payload = json.dumps({"entries": entries}, ensure_ascii=False, indent=2)
            handle.seek(0)
            handle.write(payload)
            handle.truncate()
        finally:
            _unlock(handle)
    return entry


def snapshot_point(point: dict) -> dict:
    stored = {"lat": float(point["lat"]), "lon": float(point["lon"])}
    for key in POINT_FIELDS:
        if key in point:
            stored[key] = point[key]
    return stored


def new_entry(point: dict, query: dict, cell: dict) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "at": datetime.now(timezone.utc).isoformat(),
        "point": snapshot_point(point),
        "query": query,
        "cell": cell,
    }