"""Closeness between one lunar target and the Earth land grid.

The general closeness is the mean of one score per variable, each from 0 to 1.
Which variables exist and how each one is scored come from
`data/earth/analogs.json`, and so does how much each one weighs unless the
caller passes its own weights. Adding a variable means adding a column and one
entry in that file; this module does not name any variable.

A cell with no value for a variable is not a bad match for it: the mean runs
over the variables that cell actually has, and each point reports its coverage.

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

from app.config import get_settings


def _bind_runtime_paths() -> None:
    global DATA, COLUMNS_DIR, COLUMNS, ANALOGS, SHORTLIST, EXTRACT_CMD
    paths = get_settings().paths
    DATA = paths.land_parquet
    COLUMNS_DIR = paths.columns_dir
    COLUMNS = paths.columns_json
    ANALOGS = paths.analogs
    SHORTLIST = paths.shortlist
    EXTRACT_CMD = get_settings().commands.extract_earth_columns


DATA: Path
COLUMNS_DIR: Path
COLUMNS: Path
ANALOGS: Path
SHORTLIST: Path
EXTRACT_CMD: str
_bind_runtime_paths()

SCORE_TYPES = {
    "gaussian",
    "gaussian_relative",
    "gaussian_temperature",
    "gaussian_log1p",
    "categorical",
}

# Query names that predate the contract. Kept so old clients and saved links
# keep working; the contract uses the canonical id on the right.
ALIASES = {"tmin": "temperature"}

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


def load_analogs(path: Path | None = None) -> dict:
    contract = json.loads((ANALOGS if path is None else Path(path)).read_text())
    validate_analogs(contract)
    return contract


def validate_analogs(contract: dict) -> None:
    if contract.get("schema_version") != "1.0.0":
        raise ValueError("analogs.json: schema_version no soportada")
    variables = contract.get("variables")
    if not isinstance(variables, list) or not variables:
        raise ValueError("analogs.json: falta la lista de variables")
    seen: set[str] = set()
    for spec in variables:
        name = spec.get("id")
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError("analogs.json: id vacío o duplicado")
        seen.add(name)
        if spec.get("earth_column") not in _COLUMN_ATTR:
            raise ValueError(f"analogs.json: columna desconocida en {name}")
        score = spec.get("score") or {}
        if score.get("type") not in SCORE_TYPES:
            raise ValueError(f"analogs.json: score desconocido en {name}")
        weight = spec.get("weight")
        if weight is not None and (not isinstance(weight, (int, float)) or weight < 0):
            raise ValueError(f"analogs.json: peso inválido en {name}")
        if spec.get("tier") not in {"A", "B", "C"}:
            raise ValueError(f"analogs.json: tier inválido en {name}")


def resolve_variables(
    contract: dict, criteria: dict
) -> tuple[list[tuple[dict, object]], list[str]]:
    """Contract-ordered (spec, target) pairs, plus the ids that are switched off."""
    criteria = {ALIASES.get(name, name): value for name, value in criteria.items()}
    used: list[tuple[dict, object]] = []
    ignored: list[str] = []
    known = {spec["id"] for spec in contract["variables"]}
    unknown = {
        name
        for name, value in criteria.items()
        if value is not None and value != "" and name not in known
    }
    if unknown:
        raise ValueError("variable desconocida: " + ", ".join(sorted(unknown)))
    for spec in contract["variables"]:
        value = criteria.get(spec["id"])
        if value is None or value == "":
            continue
        if not spec.get("enabled", True):
            ignored.append(spec["id"])
            continue
        used.append((spec, value))
    return used, ignored


def parse_criteria(contract: dict, values) -> dict:
    """Text values in, a criteria dict out. The contract decides each type."""
    criteria: dict[str, float | str] = {}
    for spec in contract["variables"]:
        raw = values.get(spec["id"])
        if raw is None:
            for alias, name in ALIASES.items():
                if name == spec["id"] and values.get(alias) is not None:
                    raw = values[alias]
                    break
        if raw is None or raw == "":
            continue
        if spec["score"]["type"] == "categorical":
            criteria[spec["id"]] = str(raw)
        else:
            criteria[spec["id"]] = float(raw)
    return criteria


def match_for(closeness: float) -> str:
    """The label the list, the globe and the panel show. The cuts live here only."""
    if closeness >= 0.85:
        return "very"
    if closeness >= 0.70:
        return "close"
    return "barely"


GRADE_FLOORS = ((90.0, "A"), (80.0, "B"), (70.0, "C"), (60.0, "D"))


def grade_for(closeness: float) -> str:
    """Letter grade for a 0..1 closeness, on the percentage the panel prints.

    The percentage is truncated to one decimal before the cut, so a cell that
    reads 89.9% never gets the grade for 90.
    """
    percent = math.floor(float(closeness) * 1000) / 10
    for floor, grade in GRADE_FLOORS:
        if percent >= floor:
            return grade
    return "F"


def _effective_weight(spec: dict, weights: dict[str, float | None] | None) -> float:
    """A request weight if it is a number, else the contract weight, else 1."""
    override = None if weights is None else weights.get(spec["id"])
    if isinstance(override, (int, float)) and not isinstance(override, bool):
        return float(override)
    contract_weight = spec.get("weight")
    return 1.0 if contract_weight is None else float(contract_weight)


class EarthIndex:
    def __init__(
        self, columns_dir: Path | None = None, analogs_path: Path | None = None
    ) -> None:
        directory = COLUMNS_DIR if columns_dir is None else Path(columns_dir)
        self.columns_dir = directory
        metadata_path = directory.parent / "columns.json"
        try:
            self.column_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.column_metadata = {}
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
        self.contract = load_analogs(analogs_path)
        missing = [
            spec["earth_column"]
            for spec in self.contract["variables"]
            if not hasattr(self, _COLUMN_ATTR[spec["earth_column"]])
        ]
        if missing:
            raise ValueError(
                "analogs.json pide columnas que no están en el manifiesto: "
                + ", ".join(sorted(set(missing)))
            )
        # Derived arrays live here, keyed by (transform, column). See _cache_get.
        self._cache: dict[str, np.ndarray] = {}
        # Nothing is cached across searches: every score is computed from the
        # mmap columns, so a search never holds a second copy of the grid.

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
        if spread < 0.001:
            # Every result sits on the same score, which is what happens when a
            # single variable is searched: thousands of cells tie. Show places
            # that are far apart instead of 155 neighbours with the same number.
            return self._diverse(closeness, min_closeness, limit)
        if spread >= 0.01 or len(chosen) < limit:
            return chosen
        per_band = max(3, limit // 8)
        return self._take(closeness, min_closeness, limit, step, pool=2_000_000, per_band=per_band)

    def _diverse(self, closeness: np.ndarray, min_closeness: float, limit: int) -> list[int]:
        """Greedy farthest-point sampling among the tied best cells."""
        pool = min(200_000, int(closeness.size))
        picked = np.argpartition(closeness, -pool)[-pool:]
        picked = picked[closeness[picked] >= np.float32(min_closeness)]
        if picked.size <= limit:
            return [int(index) for index in picked]
        lat = np.asarray(self.lat[picked], dtype=np.float64)
        lon = np.asarray(self.lon[picked], dtype=np.float64)
        best = int(np.argmax(closeness[picked]))
        chosen = [best]
        distance = self._planar_sq(lat, lon, best)
        for _ in range(limit - 1):
            nxt = int(np.argmax(distance))
            chosen.append(nxt)
            distance = np.minimum(distance, self._planar_sq(lat, lon, nxt))
        # Diversity decides which cells, not the order: the list still reads
        # best first.
        chosen.sort(key=lambda item: -float(closeness[picked[item]]))
        return [int(picked[index]) for index in chosen]

    @staticmethod
    def _planar_sq(lat: np.ndarray, lon: np.ndarray, index: int) -> np.ndarray:
        dlat = lat - lat[index]
        dlon = (lon - lon[index]) * math.cos(math.radians(float(lat[index])))
        return dlat * dlat + dlon * dlon

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

    # Derived arrays are computed once per column and shared by every variable
    # that asks for them. Keys are (transform, column), never variable names, so
    # a new entry in analogs.json reuses the same cache. Nothing per-variable is
    # cached: five full-grid score arrays would be 1.6 GB and push the process
    # into swap.

    CACHE_BUDGET_BYTES = 768 * 1024 * 1024

    def _cache_get(self, key: str, factory):
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        value = factory()
        if value.nbytes <= self.CACHE_BUDGET_BYTES:
            self._cache[key] = value
        return value

    def _raw(self, spec: dict) -> np.ndarray:
        return np.asarray(getattr(self, _COLUMN_ATTR[spec["earth_column"]]))

    def _space(self, spec: dict) -> np.ndarray:
        """The array the score is computed on: raw, log1p, or rock group ids."""
        column = spec["earth_column"]
        kind = spec["score"]["type"]
        raw = self._raw(spec)
        if kind == "gaussian_log1p":
            return self._cache_get(
                f"log1p:{column}",
                lambda: np.log1p(np.asarray(raw, dtype=np.float32)),
            )
        if kind == "categorical":
            return self._cache_get(
                f"groups:{column}",
                lambda: self.group_ids[np.asarray(raw).astype(np.intp)],
            )
        return raw

    @staticmethod
    def _decay(distance: np.ndarray, scale: float) -> np.ndarray:
        np.divide(distance, np.float32(scale), out=distance)
        np.negative(distance, out=distance)
        return np.exp(distance, out=distance)

    def _score_arrays(
        self,
        spec: dict,
        target,
        prepared: np.ndarray,
        raw: np.ndarray,
        *,
        want_delta: bool = False,
        out: np.ndarray | None = None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray | None, str | None]:
        """Score, presence mask, optional delta in native units, and a mode.

        Works on the full grid and on a handful of gathered cells, so the
        shortlist and its detail rows cannot drift apart. `out` lets the full
        pass reuse one buffer instead of allocating a new grid per variable.
        """
        config = spec["score"]
        kind = config["type"]

        if kind == "categorical":
            codes = rock_names()
            if target not in codes:
                raise ValueError(f"unknown rock {target}")
            rock_code = codes[target]
            target_group = int(self.group_ids[rock_code])
            group = prepared
            codes_grid = np.asarray(raw)
            if out is None:
                score = np.zeros(group.shape, dtype=np.float32)
            else:
                score = out
                score.fill(np.float32(0.0))
            score[group == target_group] = np.float32(config.get("related", 0.45))
            score[codes_grid == rock_code] = np.float32(config.get("same", 1.0))
            present = (codes_grid != 0) & (codes_grid != 15) & (group >= 0)
            return score, present, None, None

        grid = np.asarray(prepared, dtype=np.float32)
        native = np.asarray(raw, dtype=np.float32)
        present = np.isfinite(native)
        value = float(target)
        mode: str | None = None
        scale = float(config.get("scale", 1.0))

        if kind == "gaussian":
            reference = value
        elif kind == "gaussian_relative":
            scale = max(float(config["min_scale"]), abs(value) * float(config["ratio"]))
            reference = value
        elif kind == "gaussian_log1p":
            reference = float(np.log1p(value))
        elif kind == "gaussian_temperature":
            extreme = float(config["extreme_delta"])
            if value <= self.cold_ref - extreme:
                reference, mode = self.cold_ref, "relative_cold"
            elif value >= self.hot_ref + extreme:
                reference, mode = self.hot_ref, "relative_hot"
            else:
                reference, mode = value, "absolute"
        else:
            raise ValueError(f"score desconocido: {kind}")

        if out is None:
            distance = np.abs(grid - np.float32(reference))
        else:
            np.subtract(grid, np.float32(reference), out=out)
            np.abs(out, out=out)
            distance = out

        score = self._decay(distance, scale)
        # NaN * 0 is NaN, so missing cells are cleared, not multiplied by zero.
        score[~present] = np.float32(0.0)
        delta = np.abs(native - np.float32(value)) if want_delta else None
        return score, present, delta, mode

    def search(
        self,
        criteria: dict[str, float | str] | None = None,
        *,
        precision: float = 0.7,
        min_worst: float | None = None,
        weights: dict[str, float | None] | None = None,
        activity: dict | None = None,
    ) -> dict:
        criteria = {} if criteria is None else criteria
        precision = float(np.clip(precision, 0.0, 1.0))
        min_closeness = 0.55 + 0.35 * precision
        limit = int(round(40 + (1.0 - precision) * 460))

        resolved, ignored = resolve_variables(self.contract, criteria)
        # Weight 0 means the variable does not take part at all, so it never
        # reaches `variables` or `scores`. The filter lives here, not in the
        # resolver, so a caller that skips the resolver gets it too.
        used: list[tuple[dict, object, float]] = []
        for spec, target in resolved:
            weight = _effective_weight(spec, weights)
            if weight == 0.0:
                continue
            used.append((spec, target, weight))
        if not used:
            raise ValueError("falta al menos una medición")

        shape = self.lat.shape
        weighted = any(weight != 1.0 for _spec, _target, weight in used)
        total = np.zeros(shape, dtype=np.float32)
        buffer = np.empty(shape, dtype=np.float32)
        counts = np.zeros(shape, dtype=np.int8)
        weight_sum = np.zeros(shape, dtype=np.float32) if weighted else None
        temperature_mode = "not_used"

        for spec, target, weight in used:
            score, present, _delta, mode = self._score_arrays(
                spec, target, self._space(spec), self._raw(spec), out=buffer
            )
            if weight != 1.0:
                np.multiply(score, np.float32(weight), out=score)
            # Missing cells already score zero, so a plain add is correct and
            # avoids the slow masked-ufunc path.
            np.add(total, score, out=total)
            if weight_sum is not None:
                np.add(weight_sum, np.float32(weight), out=weight_sum, where=present)
            np.add(counts, present, out=counts)
            if mode is not None:
                temperature_mode = mode

        del buffer

        # A cell without a value for a variable is not a bad match for it: the
        # mean runs over what that cell has. Missing never scores zero.
        denominator = weight_sum if weight_sum is not None else counts
        # A positive sum below one is still the true weight sum. Empty cells
        # remain zero only as an internal sentinel and never pass the shortlist.
        np.divide(total, denominator, out=total, where=denominator > 0)
        closeness = total

        # Keep one place per map cell. Strict searches use small cells inside
        # the best matches. Loose searches use large cells, so the shortlist
        # reaches other regions instead of hundreds of neighboring pixels.
        step = 0.4 + (1.0 - precision) * 2.2
        chosen = np.asarray(
            self._shortlist(closeness, min_closeness, limit, step), dtype=np.int64
        )

        # Only the chosen rows need per-variable values, so the full-grid score
        # arrays are dropped before this second pass.
        detail: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray | None]] = {}
        for spec, target, _weight in used:
            prepared = self._space(spec)[chosen]
            raw = self._raw(spec)[chosen]
            score, present, delta, mode = self._score_arrays(
                spec, target, prepared, raw, want_delta=True
            )
            detail[spec["id"]] = (score, present, delta)
            if mode is not None:
                temperature_mode = mode

        points = []
        for row, index in enumerate(chosen):
            scores = {}
            score_values = {}
            grades = {}
            deltas = {}
            coverage = 0
            worst = 1.0
            for spec, _target, _weight in used:
                name = spec["id"]
                score, present, delta = detail[name]
                if not present[row]:
                    continue
                coverage += 1
                scores[name] = round(float(score[row]), 3)
                score_values[name] = float(score[row])
                grades[name] = grade_for(float(score[row]))
                worst = min(worst, float(score[row]))
                if delta is not None:
                    deltas[name] = round(float(delta[row]), 4)
            if min_worst is not None and worst < float(min_worst):
                continue
            contributions = {spec['id']: score_values[spec['id']] * weight
                             for spec, _target, weight in used if spec['id'] in score_values}
            contribution_sum = sum(contributions.values())
            shares = {key: value / contribution_sum for key, value in contributions.items()} if contribution_sum > 0 else {}
            available_weights = {spec['id']: weight for spec, _target, weight in used if spec['id'] in score_values}
            weight_sum = sum(available_weights.values())
            effective_weights = {key: weight / weight_sum for key, weight in available_weights.items()} if weight_sum > 0 else {}
            measurements = {}
            for name, array, unit, source, method_key in (
                ("elevation", self.elevation, "m", "ETOPO 2022", "grid"),
                ("slope", self.slope, "deg", "ETOPO 2022", "slope_deg"),
                ("roughness", self.roughness, "m", "ETOPO 2022", "roughness_m"),
                ("air_temperature", self.tmin, "C", "WorldClim 2.1", "tmin_coldest_month_c"),
                ("ice_thickness", self.ice, "m", "ETOPO 2022", "ice_thickness_m"),
                ("lithology", self.rock, "class", "GLiM", "lithology_code"),
            ):
                value = float(array[index]) if name != "lithology" else int(array[index])
                present = math.isfinite(value) and (name != "lithology" or value not in (0, 15))
                measurements[name] = {
                    "value": value if present else None,
                    "unit": unit,
                    "available": present,
                    "status": "valid" if present else "missing",
                    "reason": None if present else "not_available_in_index",
                    "source": source if method_key in self.column_metadata else None,
                    "method": self.column_metadata.get(method_key),
                }
            points.append(
                {
                    "lat": round(float(self.lat[index]), 4),
                    "lon": round(float(self.lon[index]), 4),
                    "closeness": round(float(closeness[index]), 4),
                    "match": match_for(float(closeness[index])),
                    "grade": grade_for(float(closeness[index])),
                    "slope_deg": round(float(self.slope[index]), 2),
                    "roughness_m": round(float(self.roughness[index]), 1),
                    "tmin_c": None if not np.isfinite(self.tmin[index]) else round(float(self.tmin[index]), 1),
                    "ice_thickness_m": round(float(self.ice[index]), 0),
                    "rock": self.labels.get(int(self.rock[index]), "?"),
                    "coverage": coverage,
                    "worst": round(worst, 4),
                    "scores": scores,
                    "score_values": score_values,
                    "weighted_shares": shares,
                    "effective_weights": effective_weights,
                    "grades": grades,
                    "deltas": deltas,
                    "row_index": int(index),
                    "coordinates_original": {"lat": float(self.lat[index]), "lon": float(self.lon[index])},
                    "measurements": measurements,
                    "quality_warnings": (["earth_slope_longitude_distance_clamped_above_83_81_deg"]
                                         if "slope" in scores and abs(float(self.lat[index])) > 83.81164256 else []),
                }
            )

        # The response always shows the weights that were used, so no caller
        # has to reshape it. Without a request weight, a variable that the
        # request asks for weighed 1, and the others weighed nothing.
        if weights is None:
            asked = {
                ALIASES.get(name, name)
                for name, value in criteria.items()
                if value is not None and value != ""
            }
            reported_weights: dict[str, float | None] = {
                spec["id"]: 1.0 if spec["id"] in asked else None
                for spec in self.contract["variables"]
            }
        else:
            reported_weights = weights

        return {
            "target": {spec["id"]: target for spec, target, _weight in used},
            "variables": [spec["id"] for spec, _target, _weight in used],
            "variables_used": [
                {
                    "id": spec["id"],
                    "tier": spec.get("tier"),
                    "weight": weight,
                    "unit": spec.get("unit"),
                }
                for spec, _target, weight in used
            ],
            "ignored": ignored,
            "weights": reported_weights,
            "activity": activity,
            "weights_version": self.contract.get("weights_version"),
            "precision": round(precision, 3),
            "min_closeness": round(min_closeness, 3),
            "min_worst": None if min_worst is None else round(float(min_worst), 3),
            "limit": limit,
            "returned": len(points),
            "closest": None if not points else max(point["closeness"] for point in points),
            "loosest": None if not points else min(point["closeness"] for point in points),
            "temperature_mode": temperature_mode,
            "points": points,
        }


def write_shortlist(result: dict) -> Path:
    SHORTLIST.write_text(json.dumps(result, indent=2))
    return SHORTLIST
