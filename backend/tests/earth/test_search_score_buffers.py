"""EarthIndex.search: masked mean, per-variable scores, and the contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "backend" / "scripts"
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
    index: EarthIndex, criteria: dict[str, float | str]
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], np.ndarray, np.ndarray, np.ndarray]:
    """Naive per-formula scores, presence masks, masked mean, coverage and worst."""
    n = int(index.lat.size)
    scores: dict[str, np.ndarray] = {}
    present: dict[str, np.ndarray] = {}
    mode = "not_used"

    for spec in index.contract["variables"]:
        name = spec["id"]
        if name not in criteria:
            continue
        target = criteria[name]
        kind = spec["score"]["type"]
        if kind == "categorical":
            codes = rock_names()
            code = codes[str(target)]
            group = index.group_ids[np.asarray(index.rock).astype(np.intp)]
            same = np.asarray(index.rock) == code
            related = (~same) & (group == int(index.group_ids[code]))
            series = np.zeros(n, dtype=np.float32)
            series[same] = np.float32(1.0)
            series[related] = np.float32(0.45)
            scores[name] = series
            present[name] = (np.asarray(index.rock) != 0) & (np.asarray(index.rock) != 15)
            continue

        grid = np.asarray(getattr(index, name)).astype(np.float32, copy=False) if False else None
        del grid
        column = {"slope": index.slope, "roughness": index.roughness,
                  "temperature": index.tmin, "ice": index.ice}[name]
        grid = np.asarray(column).astype(np.float32, copy=False)
        known = np.isfinite(grid)
        value = float(target)
        if kind == "gaussian":
            series = np.exp(-np.abs(grid - value) / np.float32(spec["score"]["scale"]))
        elif kind == "gaussian_relative":
            scale = max(float(spec["score"]["min_scale"]), abs(value) * float(spec["score"]["ratio"]))
            series = np.exp(-np.abs(grid - value) / np.float32(scale))
        elif kind == "gaussian_log1p":
            series = np.exp(
                -np.abs(np.log1p(grid) - np.float32(np.log1p(value)))
                / np.float32(spec["score"]["scale"])
            )
        elif kind == "gaussian_temperature":
            extreme = float(spec["score"]["extreme_delta"])
            if value <= index.cold_ref - extreme:
                reference, mode = index.cold_ref, "relative_cold"
            elif value >= index.hot_ref + extreme:
                reference, mode = index.hot_ref, "relative_hot"
            else:
                reference, mode = value, "absolute"
            series = np.exp(-np.abs(grid - np.float32(reference)) / np.float32(spec["score"]["scale"]))
        else:  # pragma: no cover - contract already validates the type
            raise AssertionError(kind)
        series = series.astype(np.float32)
        series[~known] = np.float32(0.0)
        scores[name] = series
        present[name] = known

    total = np.zeros(n, dtype=np.float32)
    weight = np.zeros(n, dtype=np.float32)
    worst = np.full(n, np.inf, dtype=np.float32)
    coverage = np.zeros(n, dtype=np.int8)
    for name, series in scores.items():
        mask = present[name]
        total += np.where(mask, series, np.float32(0.0))
        weight += mask.astype(np.float32)
        worst = np.where(mask, np.minimum(worst, series), worst)
        coverage += mask.astype(np.int8)
    closeness = np.zeros(n, dtype=np.float32)
    np.divide(total, weight, out=closeness, where=weight > 0)
    worst[~np.isfinite(worst)] = 0.0
    return scores, present, closeness, coverage, worst


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


def test_search_matches_reference(tiny_index: EarthIndex):
    criteria = {
        "slope": 8.0,
        "roughness": 25.0,
        "temperature": -12.0,
        "ice": 0.0,
        "rock": "vb",
    }
    scores, present, closeness, coverage, worst = _reference_scores(tiny_index, criteria)

    with patch.object(EarthIndex, "_shortlist", staticmethod(_shortlist_all_indices)):
        result = tiny_index.search(criteria, precision=0.5)

    assert result["variables"] == list(criteria)
    assert result["ignored"] == []
    assert result["weights_version"] is None
    assert [item["id"] for item in result["variables_used"]] == list(criteria)

    for row in range(int(tiny_index.lat.size)):
        point = result["points"][row]
        assert point["closeness"] == round(float(closeness[row]), 4)
        assert point["coverage"] == int(coverage[row])
        assert point["worst"] == round(float(worst[row]), 4)
        for name, series in scores.items():
            if not present[name][row]:
                assert name not in point["scores"]
                assert name not in point["deltas"]
                continue
            assert point["scores"][name] == round(float(series[row]), 3)


def test_missing_value_is_not_a_zero_score(tiny_index: EarthIndex):
    """Row 1 has no tmin. It must average over the variables it has, not be penalised."""
    criteria = {"slope": 8.0, "temperature": -12.0}
    scores, _present, closeness, coverage, _worst = _reference_scores(tiny_index, criteria)

    with patch.object(EarthIndex, "_shortlist", staticmethod(_shortlist_all_indices)):
        result = tiny_index.search(criteria, precision=0.3)

    point = result["points"][1]
    assert point["coverage"] == 1
    assert point["closeness"] == round(float(scores["slope"][1]), 4)
    assert point["closeness"] == round(float(closeness[1]), 4)
    assert coverage[1] == 1


def test_new_variable_needs_only_a_contract_entry(tmp_path, tiny_index: EarthIndex):
    """A column plus one contract entry is the whole job of adding a variable."""
    contract = json.loads((REPO_ROOT / "data" / "earth" / "analogs.json").read_text())
    contract["variables"].append(
        {
            "id": "relief",
            "earth_column": "elevation_m",
            "unit": "m",
            "tier": "A",
            "enabled": True,
            "weight": None,
            "score": {"type": "gaussian", "scale": 10.0},
        }
    )
    path = tmp_path / "analogs.json"
    path.write_text(json.dumps(contract))
    index = EarthIndex(columns_dir=Path(tiny_index.columns_dir), analogs_path=path)

    with patch.object(EarthIndex, "_shortlist", staticmethod(_shortlist_all_indices)):
        result = index.search({"relief": 100.0}, precision=0.5)

    assert result["variables"] == ["relief"]
    assert result["points"][0]["deltas"]["relief"] == 0.0
    assert result["points"][0]["scores"]["relief"] == 1.0


def test_unknown_variable_is_rejected(tiny_index: EarthIndex):
    with pytest.raises(ValueError):
        tiny_index.search({"elevation_banana": 3.0})


def test_disabled_variable_is_reported_not_scored(tmp_path, tiny_index: EarthIndex):
    contract = json.loads((REPO_ROOT / "data" / "earth" / "analogs.json").read_text())
    for spec in contract["variables"]:
        if spec["id"] == "rock":
            spec["enabled"] = False
    path = tmp_path / "analogs.json"
    path.write_text(json.dumps(contract))
    index = EarthIndex(columns_dir=Path(tiny_index.columns_dir), analogs_path=path)

    with patch.object(EarthIndex, "_shortlist", staticmethod(_shortlist_all_indices)):
        result = index.search({"slope": 8.0, "rock": "vb"}, precision=0.5)

    assert result["ignored"] == ["rock"]
    assert result["variables"] == ["slope"]
    assert "rock" not in result["points"][0]["scores"]
