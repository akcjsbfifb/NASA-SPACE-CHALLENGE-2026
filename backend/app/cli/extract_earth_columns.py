"""Stream land-grid parquet columns into raw mmap-friendly files.

Run once before serve_search / search_earth:
  .venv/bin/python -m app.cli.extract_earth_columns
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

from app.services.earth.similarity import COLUMNS_DIR, DATA

EXTRACT_SPECS: list[tuple[str, str, str]] = [
    ("lat", "lat.f32", "float32"),
    ("lon", "lon.f32", "float32"),
    ("elevation_m", "elevation_m.f32", "float32"),
    ("slope_deg", "slope_deg.f32", "float32"),
    ("roughness_m", "roughness_m.f32", "float32"),
    ("tmin_coldest_month_c", "tmin_coldest_month_c.f32", "float32"),
    ("ice_thickness_m", "ice_thickness_m.f32", "float32"),
    ("lithology_code", "lithology_code.u8", "uint8"),
]


def extract(parquet_path: Path, out_dir: Path) -> None:
    parquet_path = parquet_path.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    pf = pq.ParquetFile(parquet_path)
    rows = int(pf.metadata.num_rows)
    if rows == 0:
        raise ValueError(f"parquet has no rows: {parquet_path}")

    manifest_columns: list[dict[str, str]] = []
    for name, filename, dtype_str in EXTRACT_SPECS:
        path = out_dir / filename
        path.write_bytes(b"")
        np_dtype = np.dtype(dtype_str)
        for group in range(pf.num_row_groups):
            table = pf.read_row_group(group, columns=[name])
            chunk = table.column(0)
            array = chunk.to_numpy(zero_copy_only=False)
            if array.dtype != np_dtype:
                array = array.astype(np_dtype, copy=False)
            with path.open("ab") as handle:
                array.tofile(handle)
        expected_bytes = rows * np_dtype.itemsize
        if path.stat().st_size != expected_bytes:
            raise RuntimeError(
                f"{path.name}: wrote {path.stat().st_size} bytes, expected {expected_bytes}"
            )
        manifest_columns.append({"name": name, "file": filename, "dtype": dtype_str})

    manifest = {"rows": rows, "columns": manifest_columns}
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", type=Path, default=DATA, help="source land grid parquet")
    parser.add_argument("--out", type=Path, default=COLUMNS_DIR, help="output directory for column files")
    args = parser.parse_args()
    extract(args.parquet, args.out)


if __name__ == "__main__":
    main()