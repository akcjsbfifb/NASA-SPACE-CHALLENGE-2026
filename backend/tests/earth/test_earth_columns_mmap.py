"""EarthIndex loads column files via mmap; extractor matches manifest sizes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "backend" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from extract_earth_columns import extract  # noqa: E402
from similarity import EarthIndex  # noqa: E402


def _synthetic_parquet(path: Path) -> dict[str, np.ndarray]:
    """Five rows, north-to-south lat, duplicate latitude band, one NaN tmin."""
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


def _assert_memmap_column(array: np.ndarray, expected: np.ndarray) -> None:
    assert isinstance(array, np.memmap)
    assert array.mode == "r"
    np.testing.assert_array_equal(np.asarray(array), expected)


@pytest.fixture()
def mmap_index(tmp_path_factory):
    base = tmp_path_factory.mktemp("earth_columns_mmap")
    parquet_path = base / "tiny.parquet"
    columns_dir = base / "columns"
    expected = _synthetic_parquet(parquet_path)
    extract(parquet_path, columns_dir)
    manifest = json.loads((columns_dir / "manifest.json").read_text())
    rows = manifest["rows"]
    for entry in manifest["columns"]:
        path = columns_dir / entry["file"]
        dtype = np.dtype(entry["dtype"])
        assert path.stat().st_size == rows * dtype.itemsize
    index = EarthIndex(columns_dir=columns_dir)
    return index, expected


def test_earth_columns_mmap_load_and_query(mmap_index):
    index, expected = mmap_index
    _assert_memmap_column(index.lat, expected["lat"])
    _assert_memmap_column(index.lon, expected["lon"])
    _assert_memmap_column(index.elevation, expected["elevation_m"])
    _assert_memmap_column(index.slope, expected["slope_deg"])
    _assert_memmap_column(index.roughness, expected["roughness_m"])
    assert np.array_equal(
        np.asarray(index.tmin), expected["tmin_coldest_month_c"], equal_nan=True
    )
    assert isinstance(index.tmin, np.memmap)
    assert index.tmin.mode == "r"
    _assert_memmap_column(index.ice, expected["ice_thickness_m"])
    _assert_memmap_column(index.rock, expected["lithology_code"])

    nearest = index.nearest(45.0, -119.25)
    assert nearest is not None
    assert {"lat", "lon", "distance_km", "slope_deg", "roughness_m", "rock"} <= set(nearest)
    assert nearest["lat"] == 45.0

    result = index.search(slope=8.0, rock="vb", precision=0.5)
    assert "points" in result
    assert result["returned"] >= 1
    point = result["points"][0]
    assert "closeness" in point and "scores" in point
    assert "slope" in point["scores"] and "rock" in point["scores"]