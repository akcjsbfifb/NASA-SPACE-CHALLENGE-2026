"""EarthIndex.search: masked mean, per-variable scores, and the contract.

The `tiny_index` fixture and its five-row parquet live in conftest.py, so the
weight tests run on the same grid.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.earth.similarity import EarthIndex, rock_names  # noqa: E402


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


def test_returned_measurements_are_original_values_and_preserve_missing(tiny_index):
    with patch.object(EarthIndex, "_shortlist", staticmethod(_shortlist_all_indices)):
        result = tiny_index.search({"slope": 8.0, "roughness": 25.0}, precision=0.5)
    assert result["points"]
    for point in result["points"]:
        row = point["row_index"]
        assert point["measurements"]["slope"]["value"] == float(tiny_index.slope[row])
        assert point["measurements"]["roughness"]["value"] == float(tiny_index.roughness[row])
        assert point["coordinates_original"]["lat"] == float(tiny_index.lat[row])
        temperature = point["measurements"]["air_temperature"]
        if not np.isfinite(tiny_index.tmin[row]):
            assert temperature["value"] is None
            assert temperature["available"] is False
