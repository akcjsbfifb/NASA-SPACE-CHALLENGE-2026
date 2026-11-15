"""Shared fixtures for the Earth search tests."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.cli.extract_earth_columns import extract  # noqa: E402
from app.services.earth.similarity import EarthIndex  # noqa: E402


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


@pytest.fixture()
def tiny_index(tmp_path_factory):
    base = tmp_path_factory.mktemp("earth_search")
    parquet_path = base / "tiny.parquet"
    columns_dir = base / "columns"
    _synthetic_parquet(parquet_path)
    extract(parquet_path, columns_dir)
    return EarthIndex(columns_dir=columns_dir)