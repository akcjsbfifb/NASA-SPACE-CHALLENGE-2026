"""EarthIndex.search: request weights, zero weights, match labels, response shape."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend"
TESTS = REPO_ROOT / "backend" / "tests" / "earth"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(TESTS))

from app.cli.extract_earth_columns import extract  # noqa: E402
from app.services.earth.similarity import EarthIndex, grade_for, match_for  # noqa: E402
from test_search_score_buffers import _reference_scores, _shortlist_all_indices  # noqa: E402

ALL_WEIGHTS = ("slope", "roughness", "temperature", "ice", "rock")


def _two_cell_parquet(path: Path) -> None:
    """Cell A is close in slope and far in roughness; cell B is the other way."""
    data = {
        "lat": np.array([45.0, 45.0], dtype=np.float32),
        "lon": np.array([-120.0, -119.0], dtype=np.float32),
        "elevation_m": np.array([100.0, 100.0], dtype=np.float32),
        "slope_deg": np.array([5.0, 20.0], dtype=np.float32),
        "roughness_m": np.array([40.0, 10.0], dtype=np.float32),
        "tmin_coldest_month_c": np.array([-10.0, -10.0], dtype=np.float32),
        "ice_thickness_m": np.array([0.0, 0.0], dtype=np.float32),
        "lithology_code": np.array([2, 2], dtype=np.uint8),
    }
    table = pa.table({name: pa.array(values) for name, values in data.items()})
    pq.write_table(table, path)


@pytest.fixture()
def two_cell_index(tmp_path):
    parquet_path = tmp_path / "two_cells.parquet"
    columns_dir = tmp_path / "columns"
    _two_cell_parquet(parquet_path)
    extract(parquet_path, columns_dir)
    return EarthIndex(columns_dir=columns_dir)


def test_no_weights_keeps_the_plain_mean(tiny_index: EarthIndex):
    """Criterion 14: the default is the current unweighted mean, cell by cell."""
    criteria = {
        "slope": 8.0,
        "roughness": 25.0,
        "temperature": -12.0,
        "ice": 0.0,
        "rock": "vb",
    }
    _scores, _present, closeness, _coverage, _worst = _reference_scores(tiny_index, criteria)

    with patch.object(EarthIndex, "_shortlist", staticmethod(_shortlist_all_indices)):
        result = tiny_index.search(criteria, precision=0.5)

    for row in range(int(tiny_index.lat.size)):
        assert result["points"][row]["closeness"] == round(float(closeness[row]), 4)


def test_all_weights_one_changes_nothing(tiny_index: EarthIndex):
    """Criterion 15: five explicit 1s must land on the same numbers as no weights."""
    criteria = {"slope": 8.0, "roughness": 25.0, "temperature": -12.0}
    ones = {name: 1.0 for name in ALL_WEIGHTS}

    with patch.object(EarthIndex, "_shortlist", staticmethod(_shortlist_all_indices)):
        plain = tiny_index.search(criteria, precision=0.5)
        weighted = tiny_index.search(criteria, precision=0.5, weights=ones)

    assert [point["closeness"] for point in plain["points"]] == [
        point["closeness"] for point in weighted["points"]
    ]
    assert weighted["variables"] == plain["variables"]


def test_zero_weight_drops_the_variable_everywhere(tiny_index: EarthIndex):
    """Criterion 16: weight 0 keeps the variable out of `variables` and `scores`."""
    criteria = {
        "slope": 8.0,
        "roughness": 25.0,
        "temperature": -12.0,
        "ice": 0.0,
        "rock": "vb",
    }
    weights = {name: 1.0 for name in ALL_WEIGHTS}
    weights["slope"] = 0.0

    with patch.object(EarthIndex, "_shortlist", staticmethod(_shortlist_all_indices)):
        result = tiny_index.search(criteria, precision=0.5, weights=weights)

    assert "slope" not in result["variables"]
    assert "slope" not in result["target"]
    assert [item["id"] for item in result["variables_used"]] == result["variables"]
    assert result["weights"]["slope"] == 0
    assert result["weights"]["roughness"] == 1
    for point in result["points"]:
        assert "slope" not in point["scores"]
        assert "slope" not in point["deltas"]


def test_all_weights_zero_is_no_measurement(tiny_index: EarthIndex):
    """Criterion 17: nothing left to average is the same error as no target."""
    weights = {name: 0.0 for name in ALL_WEIGHTS}

    with pytest.raises(ValueError) as error:
        tiny_index.search({"slope": 8.0}, weights=weights)

    assert str(error.value) == "falta al menos una medición"


def test_weight_decides_which_cell_wins(two_cell_index: EarthIndex):
    """Criterion 18: slope-heavy picks A, roughness-heavy picks B. Same targets."""
    criteria = {"slope": 5.0, "roughness": 10.0}

    with patch.object(EarthIndex, "_shortlist", staticmethod(_shortlist_all_indices)):
        by_slope = two_cell_index.search(
            criteria, precision=0.5, weights={"slope": 1.0, "roughness": 0.0}
        )
        by_roughness = two_cell_index.search(
            criteria, precision=0.5, weights={"slope": 0.0, "roughness": 1.0}
        )

    assert by_slope["variables"] == ["slope"]
    assert by_roughness["variables"] == ["roughness"]

    cell_a, cell_b = by_slope["points"]
    assert cell_a["scores"]["slope"] == 1.0
    assert cell_a["closeness"] > cell_b["closeness"]

    cell_a, cell_b = by_roughness["points"]
    assert cell_b["scores"]["roughness"] == 1.0
    assert cell_b["closeness"] > cell_a["closeness"]


def test_match_for_cuts():
    """Criterion 19: the three labels, on the pure function."""
    assert match_for(0.85) == "very"
    assert match_for(0.70) == "close"
    assert match_for(0.6999) == "barely"
    assert match_for(0.8499) == "close"


def test_grade_for_cuts():
    """The letter follows the percentage the panel prints, including 89.9 vs 90."""
    assert grade_for(1.0) == "A"
    assert grade_for(0.90) == "A"
    assert grade_for(0.8999) == "B"
    assert grade_for(0.80) == "B"
    assert grade_for(0.70) == "C"
    assert grade_for(0.60) == "D"
    assert grade_for(0.5999) == "F"
    assert grade_for(0.0) == "F"


def test_response_carries_weights_activity_and_match(tiny_index: EarthIndex):
    """Criterion 20: every point has `match`; the top level has `weights` and `activity`."""
    criteria = {"slope": 8.0, "roughness": 25.0}

    with patch.object(EarthIndex, "_shortlist", staticmethod(_shortlist_all_indices)):
        result = tiny_index.search(
            criteria, precision=0.5, activity={"id": "floor_sample"}
        )
        plain = tiny_index.search(criteria, precision=0.5)

    assert result["weights"] == {
        "slope": 1.0,
        "roughness": 1.0,
        "temperature": None,
        "ice": None,
        "rock": None,
    }
    assert result["activity"] == {"id": "floor_sample"}
    assert plain["activity"] is None
    for point in result["points"]:
        assert point["match"] in {"very", "close", "barely"}
        assert point["match"] == match_for(point["closeness"])
        assert point["grade"] == grade_for(point["closeness"])
        for name, score in point["scores"].items():
            assert point["grades"][name] == grade_for(score)
