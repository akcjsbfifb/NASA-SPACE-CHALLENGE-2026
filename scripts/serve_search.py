"""Keep the Earth grid in memory and answer closeness searches.

  .venv/bin/python scripts/serve_search.py
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from similarity import EarthIndex, write_shortlist

INDEX = EarthIndex()
print(f"earth grid ready: {INDEX.lat.size:,} cells", flush=True)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/search":
            self._send(404, {"error": "not found"})
            return
        query = parse_qs(parsed.query)
        try:
            result = INDEX.search(
                slope=float(query["slope"][0]),
                roughness=float(query["roughness"][0]),
                tmin=float(query["tmin"][0]),
                ice=float(query["ice"][0]),
                rock=query["rock"][0],
                precision=float(query.get("precision", ["0.7"])[0]),
            )
        except (KeyError, ValueError) as error:
            self._send(400, {"error": str(error)})
            return
        except Exception as error:
            self._send(500, {"error": str(error)})
            return
        try:
            write_shortlist(result)
        except OSError as error:
            result = {**result, "shortlist_error": str(error)}
        self._send(200, result)

    def _send(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:
        print(f"{self.address_string()} {format % args}", flush=True)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 8787), Handler)
    print("search api http://127.0.0.1:8787/search", flush=True)
    server.serve_forever()
