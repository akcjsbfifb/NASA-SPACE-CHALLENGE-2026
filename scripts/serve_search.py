"""Keep the Earth grid in memory and answer closeness searches.

  .venv/bin/python scripts/serve_search.py
"""

from __future__ import annotations

import json
import math
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from similarity import EarthIndex, write_shortlist

INDEX = EarthIndex()
print(f"earth grid ready: {INDEX.lat.size:,} cells", flush=True)


def maps_key() -> str:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if key:
        return key
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.is_file():
        return ""
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == "GOOGLE_MAPS_API_KEY":
            return value.strip().strip('"').strip("'")
    return ""


MAPS_KEY = maps_key()
print(
    "google maps static: configured" if MAPS_KEY else "google maps static: no key, using Esri",
    flush=True,
)


def scene_bbox(lat: float, lon: float, half_m: float = 400.0) -> tuple[float, float, float, float]:
    dlat = half_m / 111_320
    dlon = half_m / max(111_320 * math.cos(math.radians(lat)), 50)
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/cell":
            self._cell(query)
            return
        if parsed.path == "/scene":
            self._scene(query)
            return
        if parsed.path != "/search":
            self._send(404, {"error": "not found"})
            return
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

    def _coordinates(self, query: dict[str, list[str]]) -> tuple[float, float]:
        return float(query["lat"][0]), float(query["lon"][0])

    def _cell(self, query: dict[str, list[str]]) -> None:
        try:
            lat, lon = self._coordinates(query)
            cell = INDEX.nearest(lat, lon)
        except (KeyError, ValueError) as error:
            self._send(400, {"error": str(error)})
            return
        except Exception as error:
            self._send(500, {"error": str(error)})
            return
        if cell is None:
            self._send(404, {"error": "no land cell"})
            return
        self._send(200, cell)

    def _scene(self, query: dict[str, list[str]]) -> None:
        try:
            lat, lon = self._coordinates(query)
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("coordinates out of range")
            payload, content_type, source = self._satellite(lat, lon)
        except (KeyError, ValueError) as error:
            self._send(400, {"error": str(error)})
            return
        except Exception as error:
            self._send(502, {"error": str(error)})
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type.split(";")[0])
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Image-Source", source)
        self.send_header("Access-Control-Expose-Headers", "X-Image-Source")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _satellite(self, lat: float, lon: float) -> tuple[bytes, str, str]:
        if MAPS_KEY:
            url = (
                "https://maps.googleapis.com/maps/api/staticmap"
                f"?center={lat},{lon}&zoom=18&size=640x480&scale=2&maptype=satellite&key={MAPS_KEY}"
            )
            try:
                image = self._fetch_image(url)
            except Exception:
                print("google scene failed, using Esri", flush=True)
                image = None
            if image is not None:
                return image[0], image[1], "google"
        west, south, east, north = scene_bbox(lat, lon)
        url = (
            "https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/export"
            f"?bbox={west},{south},{east},{north}&bboxSR=4326&size=960,720&format=jpg&f=image"
        )
        image = self._fetch_image(url)
        if image is None:
            raise RuntimeError("satellite image unavailable")
        return image[0], image[1], "esri"

    def _fetch_image(self, url: str) -> tuple[bytes, str] | None:
        request = Request(url, headers={"User-Agent": "NASA-Space-Challenge/1.0"})
        with urlopen(request, timeout=25) as response:
            payload = response.read()
            content_type = response.headers.get("Content-Type", "image/jpeg")
        if not content_type.startswith("image/"):
            return None
        return payload, content_type

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
