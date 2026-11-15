from __future__ import annotations

import sys
from pathlib import Path

from app.config import get_settings

_processing = get_settings().paths.repo_root / "backend" / "processing"
if str(_processing) not in sys.path:
    sys.path.insert(0, str(_processing))

from lunar_data.lola import LolaRaster  # noqa: E402
from lunar_data.metadata import MetadataError, load_metadata  # noqa: E402


class MoonSampler:
    """LOLA elevation and roughness for any lunar coordinate. Other variables stay absent."""

    def __init__(self) -> None:
        self.error = ""
        self.elevation: LolaRaster | None = None
        self.roughness: LolaRaster | None = None
        root = get_settings().paths.lola_raw
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