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
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "earth" / "land_60s.parquet"
COLUMNS = ROOT / "data" / "earth" / "columns.json"
SHORTLIST = ROOT / "data" / "earth" / "shortlist.json"

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
    def __init__(self) -> None:
        table = pq.read_table(
            DATA,
            columns=[
                "lat",
                "lon",
                "elevation_m",
                "slope_deg",
                "roughness_m",
                "tmin_coldest_month_c",
                "ice_thickness_m",
                "lithology_code",
            ],
        )
        self.lat = table.column("lat").to_numpy()
        self.lon = table.column("lon").to_numpy()
        self.elevation = table.column("elevation_m").to_numpy()
        self.slope = table.column("slope_deg").to_numpy()
        self.roughness = table.column("roughness_m").to_numpy()
        self.tmin = table.column("tmin_coldest_month_c").to_numpy()
        self.ice = table.column("ice_thickness_m").to_numpy()
        self.rock = table.column("lithology_code").to_numpy()
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

    def search(
        self,
        *,
        slope: float,
        roughness: float,
        tmin: float,
        ice: float,
        rock: str,
        precision: float,
    ) -> dict:
        precision = float(np.clip(precision, 0.0, 1.0))
        codes = rock_names()
        if rock not in codes:
            raise ValueError(f"unknown rock {rock}")
        rock_code = codes[rock]
        min_closeness = 0.55 + 0.35 * precision
        limit = int(round(40 + (1.0 - precision) * 460))

        slope_s = np.exp(-np.abs(self.slope - slope) / 8.0)
        rough_s = np.exp(-np.abs(self.roughness - roughness) / 50.0)
        temp_s, temp_mode = self._temperature(tmin)
        ice_s = np.exp(-np.abs(np.log1p(self.ice) - np.log1p(ice)) / 1.2)
        same = self.rock == rock_code
        related = self.group_ids[self.rock] == self.group_ids[rock_code]
        rock_s = np.where(same, 1.0, np.where(related, 0.45, 0.0)).astype(np.float32)

        closeness = ((slope_s + rough_s + temp_s + ice_s + rock_s) / 5.0).astype(np.float32)
        # Keep one place per map cell. Strict searches use small cells inside
        # the best matches. Loose searches use large cells, so the shortlist
        # reaches other regions instead of hundreds of neighboring pixels.
        step = 0.4 + (1.0 - precision) * 2.2
        pool = min(250_000, closeness.size - 1)
        picked = np.argpartition(closeness, -pool)[-pool:]
        picked = picked[np.argsort(-closeness[picked])]
        seen: set[tuple[int, int]] = set()
        chosen_list: list[int] = []
        for index in picked:
            if float(closeness[index]) < min_closeness:
                break
            cell = (int(self.lat[index] // step), int(self.lon[index] // step))
            if cell in seen:
                continue
            seen.add(cell)
            chosen_list.append(int(index))
            if len(chosen_list) == limit:
                break
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
                        "slope": round(float(slope_s[index]), 3),
                        "roughness": round(float(rough_s[index]), 3),
                        "temperature": round(float(temp_s[index]), 3),
                        "ice": round(float(ice_s[index]), 3),
                        "rock": round(float(rock_s[index]), 3),
                    },
                }
            )

        return {
            "target": {
                "slope_deg": slope,
                "roughness_m": roughness,
                "tmin_c": tmin,
                "ice_thickness_m": ice,
                "rock": rock,
            },
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
