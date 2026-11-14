"""Five-parameter closeness between one lunar target and the Earth land grid.

The general closeness is the average of five scores, each from 0 to 1:

  slope, roughness, night temperature, ice thickness, rock class

`precision` chooses the shortlist that an assistant can filter next.
1 keeps only very close places and returns a short list.
0 keeps a looser match and returns more places.
"""

from __future__ import annotations

import bisect
import json
import math
from pathlib import Path

import numpy as np
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "earth" / "land_60s.parquet"
COLUMNS_DIR = DATA.parent / "columns"
COLUMNS = ROOT / "data" / "earth" / "columns.json"
SHORTLIST = ROOT / "data" / "earth" / "shortlist.json"
EXTRACT_CMD = ".venv/bin/python scripts/extract_earth_columns.py"

_COLUMN_ATTR: dict[str, str] = {
    "lat": "lat",
    "lon": "lon",
    "elevation_m": "elevation",
    "slope_deg": "slope",
    "roughness_m": "roughness",
    "tmin_coldest_month_c": "tmin",
    "ice_thickness_m": "ice",
    "lithology_code": "rock",
}

ROCK_GROUPS: dict[str, set[int]] = {
    "volcanic": {2, 7, 10, 12},
    "plutonic": {4, 9, 13},
    "sediment": {1, 3, 5, 6},
    "metamorphic": {8},
    "evaporite": {14},
    "ice": {16},
    "water": {11},
    "unknown": {0, 15},
}


def rock_names() -> dict[str, int]:
    meta = json.loads(COLUMNS.read_text())
    coded = json.loads(meta["lithology"])
    return {abbrev: int(code) for code, abbrev in coded.items()}


def rock_labels() -> dict[int, str]:
    return {code: name for name, code in rock_names().items()}


def _group_ids() -> np.ndarray:
    ids = np.full(17, -1, dtype=np.int8)
    for index, members in enumerate(ROCK_GROUPS.values()):
        for code in members:
            ids[code] = index
    return ids


class EarthIndex:
    def __init__(self, columns_dir: Path | None = None) -> None:
        directory = COLUMNS_DIR if columns_dir is None else Path(columns_dir)
        if not directory.is_dir():
            raise FileNotFoundError(
                f"column directory missing: {directory}\n"
                f"Run: {EXTRACT_CMD}"
            )
        manifest_path = directory / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(
                f"column manifest missing: {manifest_path}\n"
                f"Run: {EXTRACT_CMD}"
            )
        manifest = json.loads(manifest_path.read_text())
        rows = int(manifest["rows"])
        for entry in manifest["columns"]:
            name = entry["name"]
            filename = entry["file"]
            dtype = np.dtype(entry["dtype"])
            path = directory / filename
            if not path.is_file():
                raise FileNotFoundError(
                    f"column file missing: {path}\n"
                    f"Run: {EXTRACT_CMD}"
                )
            expected = rows * dtype.itemsize
            actual = path.stat().st_size
            if actual != expected:
                raise ValueError(
                    f"column file size mismatch for {path.name}: "
                    f"got {actual} bytes, expected {expected} ({rows} rows x {dtype.itemsize})"
                )
            mmap = np.memmap(path, dtype=dtype, mode="r", shape=(rows,))
            setattr(self, _COLUMN_ATTR[name], mmap)
        finite = self.tmin[np.isfinite(self.tmin)]
        self.cold_ref = float(np.percentile(finite, 5))
        self.hot_ref = float(np.percentile(finite, 95))
        self.group_ids = _group_ids()
        self.labels = rock_labels()

    def nearest(self, lat: float, lon: float) -> dict | None:
        """Land cell closest to a click. Rows are stored north to south."""
        if self.lat.size == 0:
            return None
        lon = ((lon + 180.0) % 360.0) - 180.0
        seed = self._closest_lat_index(lat)
        spans = []
        seen: set[float] = set()
        for index in (seed, self._step_row(seed, -1), self._step_row(seed, 1)):
            if index is None:
                continue
            row_lat = float(self.lat[index])
            if row_lat in seen:
                continue
            seen.add(row_lat)
            spans.append(self._row_span(index))

        best: int | None = None
        best_distance = math.inf
        for start, end in spans:
            index = self._closest_lon(start, end, lon)
            distance = self._distance_km(index, lat, lon)
            if distance < best_distance:
                best = index
                best_distance = distance
        if best is None:
            return None
        return self._cell(best, best_distance)

    def _closest_lat_index(self, lat: float) -> int:
        index = bisect.bisect_left(self.lat, -lat, key=lambda value: -float(value))
        index = min(max(index, 0), int(self.lat.size) - 1)
        if index > 0 and abs(float(self.lat[index - 1]) - lat) < abs(float(self.lat[index]) - lat):
            return index - 1
        return index

    def _step_row(self, index: int, direction: int) -> int | None:
        start, end = self._row_span(index)
        neighbor = start - 1 if direction < 0 else end
        if neighbor < 0 or neighbor >= self.lat.size:
            return None
        return neighbor

    def _row_span(self, index: int) -> tuple[int, int]:
        row_lat = self.lat[index]
        start = index
        while start > 0 and self.lat[start - 1] == row_lat:
            start -= 1
        end = index + 1
        while end < self.lat.size and self.lat[end] == row_lat:
            end += 1
        return start, end

    def _closest_lon(self, start: int, end: int, lon: float) -> int:
        index = bisect.bisect_left(self.lon, lon, start, end)
        choices = [item for item in (index - 1, index) if start <= item < end]
        return min(choices, key=lambda item: abs(float(self.lon[item]) - lon))

    def _distance_km(self, index: int, lat: float, lon: float) -> float:
        scale = 111.32 * math.cos(math.radians(lat))
        dlat = (float(self.lat[index]) - lat) * 111.32
        dlon = (float(self.lon[index]) - lon) * scale
        return math.hypot(dlat, dlon)

    def _cell(self, index: int, distance_km: float) -> dict:
        tmin = float(self.tmin[index])
        elevation = float(self.elevation[index])
        return {
            "lat": round(float(self.lat[index]), 4),
            "lon": round(float(self.lon[index]), 4),
            "distance_km": round(distance_km, 2),
            "elevation_m": None if not math.isfinite(elevation) else round(elevation, 0),
            "slope_deg": round(float(self.slope[index]), 2),
            "roughness_m": round(float(self.roughness[index]), 1),
            "tmin_c": None if not math.isfinite(tmin) else round(tmin, 1),
            "ice_thickness_m": round(float(self.ice[index]), 0),
            "rock": self.labels.get(int(self.rock[index]), "?"),
        }

    def _shortlist(
        self,
        closeness: np.ndarray,
        min_closeness: float,
        limit: int,
        step: float,
    ) -> list[int]:
        """One land cell per map step, best scores first.

        When the best cells share one score, a second pass caps how many
        results can sit in the same 0.02 band and reads a wider pool. That
        keeps a 0.3 m roughness search from returning a list that is 100%
        all the way down.
        """
        chosen = self._take(closeness, min_closeness, limit, step, pool=250_000, per_band=None)
        if len(chosen) < 2:
            return chosen
        spread = float(closeness[chosen[0]] - closeness[chosen[-1]])
        if spread >= 0.01 or len(chosen) < limit:
            return chosen
        per_band = max(3, limit // 8)
        return self._take(closeness, min_closeness, limit, step, pool=2_000_000, per_band=per_band)

    def _take(
        self,
        closeness: np.ndarray,
        min_closeness: float,
        limit: int,
        step: float,
        pool: int,
        per_band: int | None,
    ) -> list[int]:
        pool = min(pool, int(closeness.size) - 1)
        picked = np.argpartition(closeness, -pool)[-pool:]
        picked = picked[np.argsort(-closeness[picked])]
        seen: set[tuple[int, int]] = set()
        band_counts: dict[int, int] = {}
        chosen: list[int] = []
        for index in picked:
            score = float(closeness[index])
            if score < min_closeness:
                break
            band = int(score / 0.02)
            if per_band is not None and band_counts.get(band, 0) >= per_band:
                continue
            cell = (int(self.lat[index] // step), int(self.lon[index] // step))
            if cell in seen:
                continue
            seen.add(cell)
            if per_band is not None:
                band_counts[band] = band_counts.get(band, 0) + 1
            chosen.append(int(index))
            if len(chosen) == limit:
                break
        return chosen

    def search(
        self,
        *,
        slope: float | None = None,
        roughness: float | None = None,
        tmin: float | None = None,
        ice: float | None = None,
        rock: str | None = None,
        precision: float = 0.7,
    ) -> dict:
        precision = float(np.clip(precision, 0.0, 1.0))
        min_closeness = 0.55 + 0.35 * precision
        limit = int(round(40 + (1.0 - precision) * 460))

        parts: list[np.ndarray] = []
        slope_s = rough_s = temp_s = ice_s = rock_s = None
        temp_mode = "not_used"
        if slope is not None:
            slope_s = np.exp(-np.abs(self.slope - slope) / 8.0)
            parts.append(slope_s)
        if roughness is not None:
            # A fixed 50 m scale scores 0.3 m and tens of meters almost the same.
            # Scale with the target: 30 m keeps the old 50 m tolerance, while
            # 0.3 m uses 0.5 m. Then 0.1 m off is about 82%, 1 m off is about 14%,
            # and 10 m off is about 0.
            rough_scale = max(0.25, abs(roughness) * (50.0 / 30.0))
            rough_s = np.exp(-np.abs(self.roughness - roughness) / rough_scale)
            parts.append(rough_s)
        if tmin is not None:
            temp_s, temp_mode = self._temperature(tmin)
            parts.append(temp_s)
        if ice is not None:
            ice_s = np.exp(-np.abs(np.log1p(self.ice) - np.log1p(ice)) / 1.2)
            parts.append(ice_s)
        if rock is not None:
            codes = rock_names()
            if rock not in codes:
                raise ValueError(f"unknown rock {rock}")
            rock_code = codes[rock]
            same = self.rock == rock_code
            related = self.group_ids[self.rock] == self.group_ids[rock_code]
            rock_s = np.where(same, 1.0, np.where(related, 0.45, 0.0)).astype(np.float32)
            parts.append(rock_s)
        if not parts:
            raise ValueError("falta al menos una medición")

        closeness = (sum(parts) / len(parts)).astype(np.float32)
        # Keep one place per map cell. Strict searches use small cells inside
        # the best matches. Loose searches use large cells, so the shortlist
        # reaches other regions instead of hundreds of neighboring pixels.
        step = 0.4 + (1.0 - precision) * 2.2
        chosen_list = self._shortlist(closeness, min_closeness, limit, step)
        chosen = np.asarray(chosen_list, dtype=np.int64)

        points = []
        for index in chosen:
            points.append(
                {
                    "lat": round(float(self.lat[index]), 4),
                    "lon": round(float(self.lon[index]), 4),
                    "closeness": round(float(closeness[index]), 4),
                    "slope_deg": round(float(self.slope[index]), 2),
                    "roughness_m": round(float(self.roughness[index]), 1),
                    "tmin_c": None if not np.isfinite(self.tmin[index]) else round(float(self.tmin[index]), 1),
                    "ice_thickness_m": round(float(self.ice[index]), 0),
                    "rock": self.labels.get(int(self.rock[index]), "?"),
                    "scores": {
                        name: round(float(series[index]), 3)
                        for name, series in (
                            ("slope", slope_s),
                            ("roughness", rough_s),
                            ("temperature", temp_s),
                            ("ice", ice_s),
                            ("rock", rock_s),
                        )
                        if series is not None
                    },
                }
            )
        used = [
            name
            for name, series in (
                ("slope", slope_s),
                ("roughness", rough_s),
                ("temperature", temp_s),
                ("ice", ice_s),
                ("rock", rock_s),
            )
            if series is not None
        ]

        return {
            "target": {
                "slope_deg": slope,
                "roughness_m": roughness,
                "tmin_c": tmin,
                "ice_thickness_m": ice,
                "rock": rock,
            },
            "variables": used,
            "precision": round(precision, 3),
            "min_closeness": round(min_closeness, 3),
            "limit": limit,
            "returned": len(points),
            "closest": None if not points else points[0]["closeness"],
            "loosest": None if not points else points[-1]["closeness"],
            "temperature_mode": temp_mode,
            "points": points,
        }

    def _temperature(self, target: float) -> tuple[np.ndarray, str]:
        known = np.isfinite(self.tmin)
        if target <= self.cold_ref - 15:
            reference = self.cold_ref
            mode = "relative_cold"
        elif target >= self.hot_ref + 15:
            reference = self.hot_ref
            mode = "relative_hot"
        else:
            reference = target
            mode = "absolute"
        score = np.zeros(self.tmin.shape, dtype=np.float32)
        score[known] = np.exp(-np.abs(self.tmin[known] - reference) / 12.0).astype(np.float32)
        return score, mode


def write_shortlist(result: dict) -> Path:
    SHORTLIST.write_text(json.dumps(result, indent=2))
    return SHORTLIST
