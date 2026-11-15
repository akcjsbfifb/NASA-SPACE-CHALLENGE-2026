from __future__ import annotations

import json
import os
import sys
import threading
import time
from collections import OrderedDict
from pathlib import Path

from app.config import get_settings

ROOT = get_settings().paths.repo_root
_processing = ROOT / "backend" / "processing"
if str(_processing) not in sys.path:
    sys.path.insert(0, str(_processing))

from lunar_data.lola import LolaRaster, normalize_coordinates
from lunar_data.metadata import MetadataError, load_metadata
from lunar_data.diviner import DivinerRaster
from lunar_data.http_range import TransferBudget
from lunar_data.lunar_prospector import LunarProspectorHydrogen


class MoonSampler:
    """Reuse the scientific readers; remote Diviner access is explicitly opt-in."""

    def __init__(self) -> None:
        self.error = ""
        self.elevation: LolaRaster | None = None
        self.roughness: LolaRaster | None = None
        root = Path(os.environ.get("LUNAR_DATA_ROOT", get_settings().paths.lola_raw))
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
