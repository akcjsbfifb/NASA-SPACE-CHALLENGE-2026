"""Keep the Earth grid in memory and answer closeness searches.

  .venv/bin/python backend/scripts/serve_search.py
"""

from __future__ import annotations

import json
import math
import os
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Empty, Queue
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from similarity import EarthIndex, write_shortlist

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "processing"))
from lunar_data.lola import LolaRaster
from lunar_data.metadata import MetadataError, load_metadata

_sse_clients: list[Queue[str]] = []
_sse_lock = threading.Lock()

NOTIFY_TOKEN_PATH = Path("/tmp/gurvich-notify.token")
MAX_NOTIFY_BODY = 2 * 1024 * 1024
NOTIFY_TOKEN = ""

_VITE_DEV_ORIGINS = frozenset(
    {
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    }
)


def init_notify_token() -> str:
    global NOTIFY_TOKEN
    token = secrets.token_urlsafe(32)
    NOTIFY_TOKEN_PATH.write_text(token)
    NOTIFY_TOKEN_PATH.chmod(0o600)
    NOTIFY_TOKEN = token
    return token


def _broadcast_search_event(body: dict) -> int:
    line = f"data: {json.dumps(body, ensure_ascii=False)}\n\n"
    with _sse_lock:
        clients = list(_sse_clients)
    for queue in clients:
        queue.put(line)
    return len(clients)


_index: EarthIndex | None = None


def earth_index() -> EarthIndex:
    global _index
    if _index is None:
        _index = EarthIndex()
        print(f"earth grid ready: {_index.lat.size:,} cells", flush=True)
    return _index


def maps_key() -> str:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if key:
        return key
    env_path = ROOT / ".env"
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


class MoonSampler:
    """LOLA elevation and roughness for any lunar coordinate. Other variables stay absent."""

    def __init__(self) -> None:
        self.error = ""
        self.elevation: LolaRaster | None = None
        self.roughness: LolaRaster | None = None
        root = ROOT / "data" / "raw" / "lola"
        try:
            self.elevation = LolaRaster(load_metadata(root / "ldem" / "ldem_16_float.xml")).__enter__()
            self.roughness = LolaRaster(load_metadata(root / "ldrm" / "ldrm_32_50_float.xml")).__enter__()
        except (OSError, MetadataError, ValueError) as error:
            self.error = str(error)

    def sample(self, lat: float, lon: float) -> dict:
        if self.error or self.elevation is None or self.roughness is None:
            raise RuntimeError(self.error or "mapas LOLA no cargados")
        elevation = self.elevation.sample(lat, lon)
        roughness = self.roughness.sample(lat, lon)
        return {
            "lat": lat,
            "lon": lon,
            "elevation_m": elevation["value"] if elevation.get("available") else None,
            "roughness_m": roughness["value"] if roughness.get("available") else None,
            "elevation_status": elevation.get("status"),
            "roughness_status": roughness.get("status"),
            "compared": ["roughness"] if roughness.get("available") else [],
            "unavailable": ["slope", "tmin", "ice", "rock"],
        }


_moon: MoonSampler | None = None


def moon_sampler() -> MoonSampler:
    global _moon
    if _moon is None:
        _moon = MoonSampler()
        print(
            "lola ready" if not _moon.error else f"lola unavailable: {_moon.error}",
            flush=True,
        )
    return _moon


def scene_bbox(lat: float, lon: float, half_m: float = 400.0) -> tuple[float, float, float, float]:
    dlat = half_m / 111_320
    dlon = half_m / max(111_320 * math.cos(math.radians(lat)), 50)
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/events":
            self._events()
            return
        if parsed.path == "/cell":
            self._cell(query)
            return
        if parsed.path == "/scene":
            self._scene(query)
            return
        if parsed.path == "/moon":
            self._moon(query)
            return
        if parsed.path != "/search":
            self._send(404, {"error": "not found"})
            return
        try:
            result = earth_index().search(
                slope=self._optional_float(query, "slope"),
                roughness=self._optional_float(query, "roughness"),
                tmin=self._optional_float(query, "tmin"),
                ice=self._optional_float(query, "ice"),
                rock=query["rock"][0] if query.get("rock") and query["rock"][0] else None,
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
        _broadcast_search_event(result)
        self._send(200, result)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/notify":
            self._send(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > MAX_NOTIFY_BODY:
            self._send(413, {"error": "payload too large"})
            return
        token = self.headers.get("X-Gurvich-Notify-Token", "")
        if not NOTIFY_TOKEN or token != NOTIFY_TOKEN:
            self._send(401, {"error": "unauthorized"})
            return
        try:
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw.decode() or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            self._send(400, {"error": str(error)})
            return
        if not isinstance(body, dict):
            self._send(400, {"error": "body must be a JSON object"})
            return
        listeners = _broadcast_search_event(body)
        self._send(200, {"listeners": listeners})

    def _events(self) -> None:
        queue: Queue[str] = Queue()
        with _sse_lock:
            _sse_clients.append(queue)
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            origin = self.headers.get("Origin", "")
            if origin in _VITE_DEV_ORIGINS:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.end_headers()
            self.wfile.write(b": ok\n\n")
            self.wfile.flush()
            while True:
                try:
                    message = queue.get(timeout=25.0)
                except Empty:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                self.wfile.write(message.encode())
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _sse_lock:
                if queue in _sse_clients:
                    _sse_clients.remove(queue)

    def _coordinates(self, query: dict[str, list[str]]) -> tuple[float, float]:
        return float(query["lat"][0]), float(query["lon"][0])

    def _optional_float(self, query: dict[str, list[str]], name: str) -> float | None:
        values = query.get(name)
        if not values or values[0] == "":
            return None
        return float(values[0])

    def _moon(self, query: dict[str, list[str]]) -> None:
        try:
            lat, lon = self._coordinates(query)
            sample = moon_sampler().sample(lat, lon)
        except (KeyError, ValueError) as error:
            self._send(400, {"error": str(error)})
            return
        except Exception as error:
            self._send(503, {"error": str(error)})
            return
        self._send(200, sample)

    def _cell(self, query: dict[str, list[str]]) -> None:
        try:
            lat, lon = self._coordinates(query)
            cell = earth_index().nearest(lat, lon)
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
    init_notify_token()
    earth_index()
    moon_sampler()
    server = ThreadingHTTPServer(("127.0.0.1", 8787), Handler)
    print("search api http://127.0.0.1:8787/search", flush=True)
    server.serve_forever()
