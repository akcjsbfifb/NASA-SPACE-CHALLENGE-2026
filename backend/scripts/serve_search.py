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
import time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Empty, Queue
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from activities import VARIABLES, ActivityError, load_catalog, resolve
from similarity import EarthIndex, parse_criteria, write_shortlist
from moon_sites import MoonSites

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "processing"))
from lunar_data.lola import LolaRaster, normalize_coordinates
from lunar_data.metadata import MetadataError, load_metadata
from lunar_data.diviner import DivinerRaster
from lunar_data.http_range import TransferBudget
from lunar_data.lunar_prospector import LunarProspectorHydrogen

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
    """Reuse the scientific readers; remote Diviner access is explicitly opt-in."""

    def __init__(self) -> None:
        self.error = ""
        self.elevation: LolaRaster | None = None
        self.roughness: LolaRaster | None = None
        root = Path(os.environ.get("LUNAR_DATA_ROOT", ROOT / "data" / "raw" / "lola"))
        self.root = root
        self.hydrogen_root = Path(os.environ.get("LUNAR_HYDROGEN_ROOT", ROOT / "data" / "raw" / "lunar_prospector" / "hydrogen"))
        self.lock = threading.Lock()
        self.cache = OrderedDict()
        registry = json.loads((ROOT / "data" / "moon" / "variables.json").read_text(encoding="utf-8"))
        self.sources = {item["id"]: {"url": item.get("source")} for item in registry["variables"] if item.get("implemented")}
        try:
            self.elevation = LolaRaster(load_metadata(root / "ldem" / "ldem_16_float.xml")).__enter__()
            self.roughness = LolaRaster(load_metadata(root / "ldrm" / "ldrm_32_50_float.xml")).__enter__()
        except (OSError, MetadataError, ValueError) as error:
            if self.elevation is not None:
                self.elevation.__exit__(None, None, None)
                self.elevation = None
            self.error = str(error)

    def sample(self, lat: float, lon: float) -> dict:
        lat, normalized_lon = normalize_coordinates(lat, lon)
        if self.error or self.elevation is None or self.roughness is None:
            raise RuntimeError(self.error or "mapas LOLA no cargados")
        with self.lock:
            cache_key = (lat, normalized_lon)
            if cache_key in self.cache:
                self.cache.move_to_end(cache_key)
                return self.cache[cache_key]
            measurements = {
                "elevation": self.elevation.sample(lat, lon),
                "roughness": self.roughness.sample(lat, lon),
                "slope": self.elevation.sample_slope(lat, lon),
            }
            try:
                with LunarProspectorHydrogen(self.hydrogen_root / "hydrogenhd.dat", self.hydrogen_root / "hydrogenhd.txt") as hydrogen:
                    measurements["hydrogen_abundance_ppm"] = hydrogen.sample(lat, lon)
            except (OSError, ValueError) as error:
                measurements["hydrogen_abundance_ppm"] = {"value": None, "unit": "ppm", "available": False, "status": "not_sampled", "reason": "source_unavailable", "source_ref": "hydrogen_abundance_ppm", "quality": {"warnings": [str(error)]}}
            budget = TransferBudget(16 * 1024 * 1024, deadline=time.monotonic() + 8)
            remote = os.environ.get("LUNAR_DIVINER_REMOTE", "").lower() in ("1", "true", "yes")
            for name, code, unit in (("rock_abundance", "ra", "1"), ("bolometric_temperature", "tbol", "K"), ("regolith_temperature", "treg", "K")):
                directory = self.root / "diviner" / name
                stem = f"dghrm_{code}_sam_70s70n_tif"
                raster = directory / (stem + ".tif")
                missing = {"value": None, "unit": unit, "available": False, "status": "not_sampled", "source_ref": name, "quality": {"warnings": []}}
                if abs(lat) > 70:
                    missing["reason"] = "outside_declared_latitude_coverage"
                    measurements[name] = missing
                    continue
                if not raster.is_file() and not remote:
                    missing["reason"] = "source_not_configured"
                    measurements[name] = missing
                    continue
                try:
                    with DivinerRaster(name, directory / (stem + ".xml"), str(raster) if raster.is_file() else None, budget) as product:
                        measurements[name] = product.sample(lat, lon)
                except Exception as error:
                    missing["reason"] = "source_unavailable"
                    missing["quality"]["warnings"].append(str(error))
                    measurements[name] = missing
        elevation = measurements["elevation"]
        roughness = measurements["roughness"]
        slope = measurements["slope"]
        result = {
            "lat": lat,
            "lon": lon,
            "normalized_coordinates": {"latitude_deg": lat, "longitude_deg": normalized_lon},
            "measurements": measurements,
            "sources": self.sources,
            "elevation_m": elevation["value"] if elevation.get("available") else None,
            "roughness_m": roughness["value"] if roughness.get("available") else None,
            "slope_deg": slope["value"] if slope.get("available") else None,
            "elevation_status": elevation.get("status"),
            "roughness_status": roughness.get("status"),
            "compared": [],
            "unavailable": [key for key, value in measurements.items() if not value.get("available")],
        }
        if all(item.get("reason") != "source_unavailable" for item in measurements.values()):
            with self.lock:
                self.cache[cache_key] = result
                self.cache.move_to_end(cache_key)
                if len(self.cache) > 64:
                    self.cache.popitem(last=False)
        return result


_moon: MoonSampler | None = None
_moon_sites: MoonSites | None = None


def moon_sites() -> MoonSites:
    global _moon_sites
    if _moon_sites is None:
        _moon_sites = MoonSites()
        print(
            f"lunar sites ready: {len(_moon_sites.sites)}"
            if not _moon_sites.error
            else f"lunar sites unavailable: {_moon_sites.error}",
            flush=True,
        )
    return _moon_sites


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
        if parsed.path == "/activities":
            self._activities()
            return
        if parsed.path != "/search":
            self._send(404, {"error": "not found"})
            return
        try:
            index = earth_index()
            values = {
                name: query[name][0]
                for name in query
                if query[name] and query[name][0] != ""
            }
            activity_id = values.pop("activity", None)
            weights = self._request_weights(values)
            targets, resolved_weights, preset = resolve(
                activity_id,
                parse_criteria(index.contract, values),
                weights,
            )
            result = index.search(
                targets,
                precision=float(values.get("precision", 0.7)),
                min_worst=self._optional_float(query, "min_worst"),
                weights=resolved_weights,
                activity={"id": preset["id"]} if preset else None,
            )
        except ActivityError as error:
            self._send(400, {"error": error.code, "message": error.message})
            return
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

    def _request_weights(self, values: dict[str, str]) -> dict[str, float]:
        """Take the w_* values out of the query and return the ones that came."""
        weights: dict[str, float] = {}
        for name in VARIABLES:
            raw = values.pop(f"w_{name}", None)
            if raw is None:
                continue
            try:
                weights[name] = float(raw)
            except ValueError:
                raise ActivityError("bad_weight", f"peso no numérico en {name}") from None
        # A w_ key outside the five is a typo, not something to ignore.
        unknown = sorted(name for name in values if name.startswith("w_"))
        if unknown:
            raise ActivityError("bad_weight", "peso desconocido: " + ", ".join(unknown))
        return weights

    def _activities(self) -> None:
        """The catalog as it is. This path never touches the Earth grid."""
        try:
            catalog = load_catalog()
        except (OSError, ValueError) as error:
            self._send(500, {"error": str(error)})
            return
        self._send(200, {"activities": catalog})

    def _moon(self, query: dict[str, list[str]]) -> None:
        site_id = (query.get("site") or [""])[0]
        if site_id:
            sites = moon_sites()
            sample = sites.find(site_id)
            if sample is None:
                self._send(404, {"error": f"unknown lunar site {site_id}"})
                return
            self._send(200, sample)
            return
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
    moon_sites()
    port = int(os.environ.get("SEARCH_PORT", "8787"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"search api http://127.0.0.1:{port}/search", flush=True)
    server.serve_forever()
