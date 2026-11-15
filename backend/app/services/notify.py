from __future__ import annotations

import json
import secrets
import threading
from queue import Queue

from app.config import get_settings

_sse_clients: list[Queue[str]] = []
_sse_lock = threading.Lock()

NOTIFY_TOKEN = ""
MAX_NOTIFY_BODY = 2 * 1024 * 1024


def configure_limits() -> None:
    global MAX_NOTIFY_BODY
    MAX_NOTIFY_BODY = get_settings().server.max_notify_body_bytes


def init_notify_token() -> str:
    global NOTIFY_TOKEN
    path = get_settings().paths.notify_token
    token = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token)
    path.chmod(0o600)
    NOTIFY_TOKEN = token
    return token


def broadcast_search_event(body: dict) -> int:
    line = f"data: {json.dumps(body, ensure_ascii=False)}\n\n"
    with _sse_lock:
        clients = list(_sse_clients)
    for queue in clients:
        queue.put(line)
    return len(clients)


def register_sse_client() -> Queue[str]:
    queue: Queue[str] = Queue()
    with _sse_lock:
        _sse_clients.append(queue)
    return queue


def unregister_sse_client(queue: Queue[str]) -> None:
    with _sse_lock:
        if queue in _sse_clients:
            _sse_clients.remove(queue)

