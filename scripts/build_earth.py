"""Build a filterable global land grid for Moon/Mars analog search.

Each row is one land cell of ETOPO 2022 at 60 arc-seconds (~1.8 km).
Columns are the Earth side of the five analog variables:

  slope_deg               terrain slope
  roughness_m             elevation scatter in a 3x3 window
  lithology_code          surface rock class (GLiM)
  tmin_coldest_month_c    coldest-month daily minimum air temperature
  ice_thickness_m         ice-sheet thickness, the ice/hydrogen proxy

ETOPO is read in horizontal strips, so the process stays near a few
hundred MB instead of holding several full-Earth copies in RAM.

Run:
  .venv/bin/python scripts/build_earth.py
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import rasterio

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "earth" / "land_60s.parquet"

LITHOLOGY = {
    1: "su",
    2: "vb",
    3: "ss",
    4: "pb",
    5: "sm",
    6: "sc",
    7: "va",
    8: "mt",
    9: "pa",
    10: "vi",
    11: "wb",
    12: "py",
    13: "pi",
    14: "ev",
    15: "nd",
    16: "ig",
}

LITHOLOGY_NAME = {
    "su": "unconsolidated sediment",
    "vb": "basic volcanic (basalt)",
    "ss": "siliciclastic sedimentary",
    "pb": "basic plutonic",
    "sm": "mixed sedimentary",
    "sc": "carbonate sedimentary",
    "va": "acid volcanic",
    "mt": "metamorphic",
    "pa": "acid plutonic",
    "vi": "intermediate volcanic",
    "wb": "water",
    "py": "pyroclastic",
    "pi": "intermediate plutonic",
    "ev": "evaporite",
    "nd": "no data",
    "ig": "ice and glaciers",
}


STRIP_ROWS = 256


def read_window(src: rasterio.DatasetReader, row0: int, row1: int) -> np.ndarray:
    window = rasterio.windows.Window(0, row0, src.width, row1 - row0)
    elev = src.read(1, window=window).astype(np.float32, copy=False)
    nodata = src.nodata
    if nodata is not None:
        elev[elev == np.float32(nodata)] = np.nan
    elev[~np.isfinite(elev)] = np.nan
    return elev


def with_halo(elev: np.ndarray, row0: int, row1: int, height: int) -> np.ndarray:
    """One-pixel border. The outer rows of the Earth are copied, matching edge padding."""
    if row0 == 0:
        elev = np.concatenate([elev[:1], elev], axis=0)
    if row1 == height:
        elev = np.concatenate([elev, elev[-1:]], axis=0)
    return np.pad(elev, ((0, 0), (1, 1)), mode="edge")


def slope_and_roughness(padded: np.ndarray, transform: rasterio.Affine, row0: int) -> tuple[np.ndarray, np.ndarray]:
    """Slope and roughness. Missing neighbors are treated as flat, so coasts
    are not turned into cliffs by the ocean fill.

    `padded` includes a one-pixel halo on every side.
    """
    center = padded[1:-1, 1:-1]
    height, _width = center.shape
    lat = transform.f + (np.arange(row0, row0 + height, dtype=np.float64) + 0.5) * transform.e
    meters_per_degree = 111_320.0
    dy = abs(float(transform.e)) * meters_per_degree
    dx = abs(float(transform.a)) * meters_per_degree * np.cos(np.deg2rad(lat))
    dx = np.maximum(dx, 200.0)

    north = np.where(np.isfinite(padded[:-2, 1:-1]), padded[:-2, 1:-1], center)
    south = np.where(np.isfinite(padded[2:, 1:-1]), padded[2:, 1:-1], center)
    west = np.where(np.isfinite(padded[1:-1, :-2]), padded[1:-1, :-2], center)
    east = np.where(np.isfinite(padded[1:-1, 2:]), padded[1:-1, 2:], center)

    dz_dy = (north - south) / (2.0 * dy)
    dz_dx = (east - west) / (2.0 * dx[:, None])
    slope = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy))).astype(np.float32)
    slope[~np.isfinite(center)] = np.nan

    accum = np.zeros(center.shape, dtype=np.float32)
    count = np.zeros(center.shape, dtype=np.float32)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            if di == 0 and dj == 0:
                continue
            neighbor = padded[1 + di : 1 + di + height, 1 + dj : 1 + dj + center.shape[1]]
            valid = np.isfinite(neighbor) & np.isfinite(center)
            diff = np.where(valid, neighbor - center, 0.0)
            accum += diff * diff
            count += valid.astype(np.float32)
    roughness = np.sqrt(accum / np.maximum(count, 1.0)).astype(np.float32)
    roughness[~np.isfinite(center)] = np.nan
    return slope, roughness


def land_mask(surface: np.ndarray, bed: np.ndarray, climate_land: np.ndarray) -> np.ndarray:
    """Keep WorldClim land (includes basins below sea level) and ice sheets.

    ETOPO stores ocean as bathymetry, with surface equal to bedrock, so a
    depth threshold cannot separate the Dead Sea from the continental shelf.
    WorldClim is already masked to land. Ice thicker than 50 m is kept even
    where that climate mask is empty.
    """
    ice_sheet = (surface - bed) > 50
    return np.isfinite(surface) & (climate_land | ice_sheet)


def load_coldest_tmin() -> tuple[np.ndarray, rasterio.Affine]:
    paths = sorted((RAW / "worldclim").glob("wc2.1_10m_tmin_*.tif"))
    if len(paths) != 12:
        raise SystemExit(f"expected 12 WorldClim tmin grids, found {len(paths)}")
    stack = None
    wc_transform = None
    for path in paths:
        with rasterio.open(path) as src:
            band = src.read(1).astype(np.float32, copy=False)
            wc_transform = src.transform
            print(f"{path.name}: {src.width}x{src.height}")
        band[band < -100] = np.nan
        finite = band[np.isfinite(band)]
        if finite.size and float(np.nanmax(np.abs(finite))) > 80:
            band = band / 10.0
        stack = band if stack is None else np.fmin(stack, np.where(np.isfinite(band), band, stack))
    assert stack is not None and wc_transform is not None
    return stack, wc_transform


def sample_tmin(
    stack: np.ndarray,
    wc_transform: rasterio.Affine,
    rows: np.ndarray,
    cols: np.ndarray,
    surface_transform: rasterio.Affine,
) -> np.ndarray:
    lat = surface_transform.f + (rows + 0.5) * surface_transform.e
    lon = surface_transform.c + (cols + 0.5) * surface_transform.a
    wc_row = np.floor((wc_transform.f - lat) / abs(float(wc_transform.e))).astype(np.int32)
    wc_col = np.floor((lon - float(wc_transform.c)) / abs(float(wc_transform.a))).astype(np.int32)
    wc_row = np.clip(wc_row, 0, stack.shape[0] - 1)
    wc_col = np.clip(wc_col, 0, stack.shape[1] - 1)
    return stack[wc_row, wc_col].astype(np.float32)


def load_lithology() -> np.ndarray:
    path = RAW / "glim" / "glim_wgs84_0point5deg.txt.asc"
    grid = np.loadtxt(path, skiprows=6, dtype=np.float32)
    if grid.shape != (360, 720):
        raise SystemExit(f"unexpected GLiM shape {grid.shape}")
    grid[grid < 0] = 0
    return grid.astype(np.uint8)


def sample_lithology(grid: np.ndarray, rows: np.ndarray, cols: np.ndarray, transform: rasterio.Affine) -> np.ndarray:
    lat = transform.f + (rows + 0.5) * transform.e
    lon = transform.c + (cols + 0.5) * transform.a
    # ASCII grid origin is the south-west corner; the first row is the north edge.
    grow = np.floor((90.0 - lat) / 0.5).astype(np.int32)
    gcol = np.floor((lon + 180.0) / 0.5).astype(np.int32)
    grow = np.clip(grow, 0, grid.shape[0] - 1)
    gcol = np.clip(gcol, 0, grid.shape[1] - 1)
    return grid[grow, gcol]


def main() -> None:
    started = time.perf_counter()
    surface_path = RAW / "ETOPO_2022_v1_60s_surface.tif"
    bed_path = RAW / "ETOPO_2022_v1_60s_bed.tif"
    tmin_grid, tmin_transform = load_coldest_tmin()
    climate = np.isfinite(tmin_grid)
    lithology_grid = load_lithology()
    meta = {
        "grid": "ETOPO 2022 v1, 60 arc-second, land and ice sheets",
        "slope_deg": "gradient of surface elevation, degrees, ~1.8 km baseline",
        "roughness_m": "RMS elevation difference to the 8 neighbors, meters, ~5.5 km window",
        "tmin_coldest_month_c": "WorldClim 2.1 10 arc-minute coldest-month mean daily minimum air temperature, degrees C. Null where WorldClim has no land value (Antarctica).",
        "ice_thickness_m": "ETOPO surface minus bedrock where thicker than 50 m. Proxy for ground ice, not neutron-derived soil hydrogen. 0 means no ice sheet.",
        "lithology_code": "GLiM v1 0.5 degree class (Hartmann & Moosdorf 2012). 0 = ocean or no data.",
        "lithology": json.dumps(LITHOLOGY),
        "lithology_name": json.dumps(LITHOLOGY_NAME),
    }
    schema = pa.schema(
        [
            ("lat", pa.float32()),
            ("lon", pa.float32()),
            ("elevation_m", pa.float32()),
            ("slope_deg", pa.float32()),
            ("roughness_m", pa.float32()),
            ("tmin_coldest_month_c", pa.float32()),
            ("ice_thickness_m", pa.float32()),
            ("lithology_code", pa.uint8()),
        ],
        metadata={key: value.encode() for key, value in meta.items()},
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUT.with_suffix(".parquet.building")
    rows_written = 0

    with rasterio.open(surface_path) as surface_src, rasterio.open(bed_path) as bed_src:
        height, width = surface_src.height, surface_src.width
        transform = surface_src.transform
        print(f"{surface_path.name}: {surface_src.width}x{surface_src.height} {surface_src.crs} nodata={surface_src.nodata}")
        print(f"{bed_path.name}: {bed_src.width}x{bed_src.height} {bed_src.crs} nodata={bed_src.nodata}")
        if (bed_src.height, bed_src.width) != (height, width) or bed_src.transform != transform:
            raise SystemExit("surface and bed grids do not align")
        if climate.shape[0] * 10 != height or climate.shape[1] * 10 != width:
            raise SystemExit(f"WorldClim grid {climate.shape} is not 10x ETOPO {(height, width)}")

        with pq.ParquetWriter(temporary, schema, compression="zstd") as writer:
            for row0 in range(0, height, STRIP_ROWS):
                row1 = min(height, row0 + STRIP_ROWS)
                read0 = row0 if row0 == 0 else row0 - 1
                read1 = row1 if row1 == height else row1 + 1
                surface = with_halo(read_window(surface_src, read0, read1), row0, row1, height)
                bed = with_halo(read_window(bed_src, read0, read1), row0, row1, height)
                interior = surface[1:-1, 1:-1]
                bed_interior = bed[1:-1, 1:-1]
                climate_strip = np.repeat(climate[np.arange(row0, row1) // 10], 10, axis=1)
                mask = land_mask(interior, bed_interior, climate_strip)
                ice = np.clip(interior - bed_interior, 0, None).astype(np.float32)
                ice[ice < 50] = 0
                ice[~mask] = np.nan
                slope, roughness = slope_and_roughness(surface, transform, row0)
                flat = np.flatnonzero(mask)
                if flat.size:
                    local_rows = (flat // width).astype(np.int32)
                    cols = (flat % width).astype(np.int32)
                    rows = local_rows + np.int32(row0)
                    lat = (transform.f + (rows + 0.5) * transform.e).astype(np.float32)
                    lon = (transform.c + (cols + 0.5) * transform.a).astype(np.float32)
                    writer.write_table(
                        pa.table(
                            {
                                "lat": lat,
                                "lon": lon,
                                "elevation_m": interior.ravel()[flat],
                                "slope_deg": slope.ravel()[flat],
                                "roughness_m": roughness.ravel()[flat],
                                "tmin_coldest_month_c": sample_tmin(tmin_grid, tmin_transform, rows, cols, transform),
                                "ice_thickness_m": ice.ravel()[flat],
                                "lithology_code": sample_lithology(lithology_grid, rows, cols, transform),
                            },
                            schema=schema,
                        )
                    )
                    rows_written += int(flat.size)
                if row0 % (STRIP_ROWS * 8) == 0:
                    print(f"rows {row0:,}/{height:,} land cells {rows_written:,}", flush=True)

    print_spot_checks(temporary)
    temporary.replace(OUT)
    (OUT.parent / "columns.json").write_text(json.dumps(meta | {"rows": rows_written}, indent=2))
    elapsed = time.perf_counter() - started
    print(f"wrote {OUT} rows={rows_written:,} bytes={OUT.stat().st_size:,} in {elapsed:.1f}s")


def print_spot_checks(path: Path) -> None:
    checks = {
        "atacama": (-24.5, -69.25),
        "death_valley": (36.24, -116.82),
        "iceland": (64.8, -18.0),
        "mcmurdo": (-77.84, 166.67),
    }
    best = {name: None for name in checks}
    best_dist = {name: math.inf for name in checks}
    for batch in pq.ParquetFile(path).iter_batches(batch_size=500_000):
        lat = batch.column("lat").to_numpy()
        lon = batch.column("lon").to_numpy()
        for name, (clat, clon) in checks.items():
            dist = (lat - clat) ** 2 + (lon - clon) ** 2
            index = int(np.argmin(dist))
            if float(dist[index]) < best_dist[name]:
                best_dist[name] = float(dist[index])
                best[name] = {column: batch.column(column)[index].as_py() for column in batch.schema.names}
    for name, row in best.items():
        if row is None:
            continue
        tmin = row["tmin_coldest_month_c"]
        tmin_txt = "null" if tmin is None or tmin != tmin else f"{tmin:.1f}"
        print(
            f"check {name}: {row['lat']:.3f},{row['lon']:.3f} "
            f"elev={row['elevation_m']:.0f} "
            f"slope={row['slope_deg']:.2f} "
            f"rough={row['roughness_m']:.1f} "
            f"tmin={tmin_txt} "
            f"ice={row['ice_thickness_m']:.0f} "
            f"rock={LITHOLOGY.get(int(row['lithology_code']), '?')}"
        )


if __name__ == "__main__":
    main()
