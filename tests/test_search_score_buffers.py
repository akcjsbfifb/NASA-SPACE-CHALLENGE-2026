"""EarthIndex.search score buffers and session cache vs naive reference."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from extract_earth_columns import extract  # noqa: E402
from similarity import EarthIndex, rock_names  # noqa: E402


def _synthetic_parquet(path: Path) -> dict[str, np.ndarray]:
    data = {
        "lat": np.array([45.0, 45.0, 45.0, 30.0, 10.0], dtype=np.float32),
        "lon": np.array([-120.0, -119.5, -119.0, 10.0, 20.0], dtype=np.float32),
        "elevation_m": np.array([100.0, 110.0, 90.0, 50.0, 0.0], dtype=np.float32),
        "slope_deg": np.array([5.0, 8.0, 12.0, 3.0, 1.0], dtype=np.float32),
        "roughness_m": np.array([20.0, 25.0, 30.0, 10.0, 5.0], dtype=np.float32),
        "tmin_coldest_month_c": np.array([-15.0, np.nan, -12.0, -5.0, 5.0], dtype=np.float32),
        "ice_thickness_m": np.array([0.0, 0.0, 50.0, 0.0, 0.0], dtype=np.float32),
        "lithology_code": np.array([2, 2, 7, 1, 16], dtype=np.uint8),
    }
    table = pa.table({name: pa.array(values) for name, values in data.items()})
    pq.write_table(table, path)
    return data


def _reference_scores(
    index: EarthIndex,
    *,
    slope: float,
    roughness: float,
    tmin: float,
    ice: float,
    rock: str,
) -> tuple[dict[str, np.ndarray], np.ndarray, str]:
    """Naive per-formula scores on all rows (float32 where ice uses cached-style ops)."""
    n = int(index.lat.size)
    parts: list[np.ndarray] = []
    scores: dict[str, np.ndarray] = {}

    slope_s = np.exp(-np.abs(np.asarray(index.slope, dtype=np.float32) - slope) / 8.0).astype(
        np.float32
    )
    scores["slope"] = slope_s
    parts.append(slope_s)

    rough_scale = max(0.25, abs(roughness) * (50.0 / 30.0))
    rough_s = np.exp(
        -np.abs(np.asarray(index.roughness, dtype=np.float32) - roughness) / rough_scale
    ).astype(np.float32)
    scores["roughness"] = rough_s
    parts.append(rough_s)

    grid_tmin = np.asarray(index.tmin, dtype=np.float32)
    known = np.isfinite(grid_tmin)
    if tmin <= index.cold_ref - 15:
        reference = index.cold_ref
        mode = "relative_cold"
    elif tmin >= index.hot_ref + 15:
        reference = index.hot_ref
        mode = "relative_hot"
    else:
        reference = tmin
        mode = "absolute"
    temp_s = np.zeros(n, dtype=np.float32)
    temp_s[known] = np.exp(-np.abs(grid_tmin[known] - reference) / 12.0).astype(np.float32)
    scores["temperature"] = temp_s
    parts.append(temp_s)

    log_ice_grid = np.log1p(np.asarray(index.ice, dtype=np.float32))
    log_ice_target = np.float32(np.log1p(float(ice)))
    ice_s = np.exp(-np.abs(log_ice_grid - log_ice_target) / np.float32(1.2)).astype(np.float32)
    scores["ice"] = ice_s
    parts.append(ice_s)

    codes = rock_names()
    rock_code = codes[rock]
    group_ids = index.group_ids
    target_group = int(group_ids[rock_code])
    rock_grid = np.asarray(index.rock)
    cell_group = group_ids[rock_grid.astype(np.intp)]
    same = rock_grid == rock_code
    rock_s = np.zeros(n, dtype=np.float32)
    rock_s[same] = np.float32(1.0)
    rock_s[(~same) & (cell_group == target_group)] = np.float32(0.45)
    scores["rock"] = rock_s
    parts.append(rock_s)

    closeness = np.array(parts[0], dtype=np.float32, copy=True)
    for part in parts[1:]:
        closeness += part
    closeness /= np.float32(len(parts))
    return scores, closeness, mode


@pytest.fixture()
def tiny_index(tmp_path_factory):
    base = tmp_path_factory.mktemp("search_score_buffers")
    parquet_path = base / "tiny.parquet"
    columns_dir = base / "columns"
    _synthetic_parquet(parquet_path)
    extract(parquet_path, columns_dir)
    return EarthIndex(columns_dir=columns_dir)


def _shortlist_all_indices(
    closeness: np.ndarray,
    min_closeness: float,
    limit: int,
    step: float,
) -> list[int]:
    del min_closeness, limit, step
    return list(range(int(closeness.size)))


def test_search_matches_reference_and_reuses_cache(tiny_index: EarthIndex):
    params = dict(
        slope=8.0,
        roughness=25.0,
        tmin=-12.0,
        ice=0.0,
        rock="vb",
        precision=0.5,
    )
    score_params = {k: params[k] for k in ("slope", "roughness", "tmin", "ice", "rock")}
    ref_scores, ref_closeness, ref_mode = _reference_scores(tiny_index, **score_params)

    with patch.object(EarthIndex, "_shortlist", staticmethod(_shortlist_all_indices)):
        first = tiny_index.search(**params)
    ice_cache = tiny_index._ice_log1p
    rock_cache = tiny_index._rock_group_id
    tmin_cache = tiny_index._tmin_finite
    assert ice_cache is not None and rock_cache is not None and tmin_cache is not None
    assert tiny_index._search_cache_ready

    with patch.object(EarthIndex, "_shortlist", staticmethod(_shortlist_all_indices)):
        second = tiny_index.search(**params)
    assert tiny_index._ice_log1p is ice_cache
    assert tiny_index._rock_group_id is rock_cache
    assert tiny_index._tmin_finite is tmin_cache

    assert first["temperature_mode"] == ref_mode
    assert second["temperature_mode"] == ref_mode

    by_index_first = {i: first["points"][i] for i in range(len(first["points"]))}
    for row in range(int(tiny_index.lat.size)):
        point = by_index_first[row]
        assert point["closeness"] == round(float(ref_closeness[row]), 4)
        for name, ref_series in ref_scores.items():
            assert point["scores"][name] == round(float(ref_series[row]), 3)

    assert ice_cache.dtype == np.float32
    assert rock_cache.dtype == np.int8
    assert tmin_cache.dtype == bool