from __future__ import annotations

import math
import os
from pathlib import Path
from urllib.request import Request, urlopen

from app.config import get_settings


def maps_key() -> str:
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if key:
        return key
    env_path = get_settings().paths.repo_root / ".env"
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


def scene_bbox(lat: float, lon: float, half_m: float = 400.0) -> tuple[float, float, float, float]:
    dlat = half_m / 111_320
    dlon = half_m / max(111_320 * math.cos(math.radians(lat)), 50)
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def fetch_image(url: str) -> tuple[bytes, str] | None:
    request = Request(url, headers={"User-Agent": "NASA-Space-Challenge/1.0"})
    with urlopen(request, timeout=25) as response:
        payload = response.read()
        content_type = response.headers.get("Content-Type", "image/jpeg")
    if not content_type.startswith("image/"):
        return None
    return payload, content_type


def satellite_scene(lat: float, lon: float, maps_api_key: str) -> tuple[bytes, str, str]:
    if maps_api_key:
        url = (
            "https://maps.googleapis.com/maps/api/staticmap"
            f"?center={lat},{lon}&zoom=18&size=640x480&scale=2&maptype=satellite&key={maps_api_key}"
        )
        try:
            image = fetch_image(url)
        except Exception:
            image = None
        if image is not None:
            return image[0], image[1], "google"
    west, south, east, north = scene_bbox(lat, lon)
    url = (
        "https://services.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/export"
        f"?bbox={west},{south},{east},{north}&bboxSR=4326&size=960,720&format=jpg&f=image"
    )
    image = fetch_image(url)
    if image is None:
        raise RuntimeError("satellite image unavailable")
    return image[0], image[1], "esri"