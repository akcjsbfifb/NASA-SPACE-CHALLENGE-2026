"""Measured values for named lunar sites, read from the published JSON.

The JSON is produced offline by `python -m lunar_data --sites ...` and is the
only file the API needs at runtime: answering for a known landing site does not
need the LOLA originals or the geospatial stack.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SITES_PATH = ROOT / "data" / "moon" / "apollo_measurements.json"

# The seven magnitudes the processor can produce. Everything else in the
# document (mineralogy, landing safety, ...) is out of scope for this adapter.
MEASURED = (
    "elevation",
    "roughness",
    "slope",
    "rock_abundance",
    "bolometric_temperature",
    "regolith_temperature",
    "hydrogen_abundance_ppm",
)

# Flat keys the moon panel already reads, kept for the current frontend.
FLAT = {"elevation": "elevation_m", "roughness": "roughness_m", "slope": "slope_deg"}


class MoonSites:
    """Lookup by id. A missing or broken file never raises at import time."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = SITES_PATH if path is None else Path(path)
        self.error = ""
        self.sites: dict[str, dict] = {}
        try:
            document = json.loads(self.path.read_text())
        except (OSError, ValueError) as error:
            self.error = str(error)
            return
        for site in document.get("sites", []):
            site_id = site.get("id")
            if not isinstance(site_id, str):
                continue
            self.sites[site_id] = site

    def find(self, site_id: str) -> dict | None:
        site = self.sites.get(site_id)
        if site is None:
            return None
        measurements = site.get("measurements", {})
        selected = {
            key: {
                "available": item.get("available"),
                "value": item.get("value"),
                "unit": item.get("unit"),
                "status": item.get("status"),
                "reason": item.get("reason"),
            }
            for key, item in measurements.items()
            if key in MEASURED
        }
        payload = {
            "site": site["id"],
            "name": site.get("name", site["id"]),
            "source": site.get("source"),
            "is_example": site.get("is_example"),
            "lat": site.get("requested_coordinates", {}).get("latitude_deg"),
            "lon": site.get("requested_coordinates", {}).get("longitude_deg"),
            "measurements": selected,
            "compared": [
                key for key in MEASURED if selected.get(key, {}).get("available") is True
            ],
            "unavailable": [
                key for key in MEASURED if selected.get(key, {}).get("available") is not True
            ],
        }
        for key, flat in FLAT.items():
            item = selected.get(key, {})
            payload[flat] = item.get("value") if item.get("available") is True else None
            payload[f"{key}_status"] = item.get("status")
        return payload
