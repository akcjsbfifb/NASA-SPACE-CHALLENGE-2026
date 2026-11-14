"""Build a filterable global land grid for Moon/Mars analog search.

Each row is one land cell of ETOPO 2022 at 60 arc-seconds (~1.8 km).
Columns are the Earth side of the five analog variables:

  slope_deg               terrain slope
  roughness_m             elevation scatter in a 3x3 window
  lithology_code          surface rock class (GLiM)
  tmin_coldest_month_c    coldest-month daily minimum air temperature
  ice_thickness_m         ice-sheet thickness, the ice/hydrogen proxy

Run:
  .venv/bin/python scripts/build_earth.py
"""

from __future__ import annotations

import json
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


def load_dem(path: Path) -> tuple[np.ndarray, rasterio.Affine]:
    with rasterio.open(path) as src:
        elev = src.read(1).astype(np.float32, copy=False)
        transform = src.transform
        nodata = src.nodata
        print(f"{path.name}: {src.width}x{src.height} {src.crs} nodata={nodata}")
    if nodata is not None:
        elev[elev == np.float32(nodata)] = np.nan
    elev[~np.isfinite(elev)] = np.nan
    return elev, transform


def slope_and_roughness(elev: np.ndarray, transform: rasterio.Affine) -> tuple[np.ndarray, np.ndarray]:
    """Slope and roughness. Missing neighbors are treated as flat, so coasts
    are not turned into cliffs by the ocean fill."""
    height, width = elev.shape
    lat = transform.f + (np.arange(height, dtype=np.float64) + 0.5) * transform.e
    meters_per_degree = 111_320.0
    dy = abs(float(transform.e)) * meters_per_degree
    dx = abs(float(transform.a)) * meters_per_degree * np.cos(np.deg2rad(lat))
    dx = np.maximum(dx, 200.0)

    padded = np.pad(elev, 1, mode="edge")
    center = padded[1:-1, 1:-1]
    north = padded[:-2, 1:-1]
    south = padded[2:, 1:-1]
    west = padded[1:-1, :-2]
    east = padded[1:-1, 2:]
    north = np.where(np.isfinite(north), north, center)
    south = np.where(np.isfinite(south), south, center)
    west = np.where(np.isfinite(west), west, center)
    east = np.where(np.isfinite(east), east, center)

    dz_dy = (north - south) / (2.0 * dy)
    dz_dx = (east - west) / (2.0 * dx[:, None])
    slope = np.degrees(np.arctan(np.hypot(dz_dx, dz_dy))).astype(np.float32)
    slope[~np.isfinite(elev)] = np.nan

    accum = np.zeros((height, width), dtype=np.float32)
    count = np.zeros((height, width), dtype=np.float32)
    for di in (-1, 0, 1):
        for dj in (-1, 0, 1):
            if di == 0 and dj == 0:
                continue
            neighbor = padded[1 + di : 1 + di + height, 1 + dj : 1 + dj + width]
            valid = np.isfinite(neighbor) & np.isfinite(center)
            diff = np.where(valid, neighbor - center, 0.0)
            accum += diff * diff
            count += valid.astype(np.float32)
    roughness = np.sqrt(accum / np.maximum(count, 1.0)).astype(np.float32)
    roughness[~np.isfinite(elev)] = np.nan
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
    surface, transform = load_dem(surface_path)
    bed, bed_transform = load_dem(bed_path)
    if bed.shape != surface.shape or bed_transform != transform:
        raise SystemExit("surface and bed grids do not align")

    tmin_grid, tmin_transform = load_coldest_tmin()
    climate_land = np.isfinite(tmin_grid)
    if climate_land.shape[0] * 10 == surface.shape[0] and climate_land.shape[1] * 10 == surface.shape[1]:
        climate_land = np.repeat(np.repeat(climate_land, 10, axis=0), 10, axis=1)
    else:
        raise SystemExit(f"WorldClim grid {climate_land.shape} is not 10x ETOPO {surface.shape}")
    mask = land_mask(surface, bed, climate_land)
    del climate_land
    ice = np.clip(surface - bed, 0, None).astype(np.float32)
    ice[ice < 50] = 0
    ice[~mask] = np.nan
    del bed

    print(f"land cells: {int(mask.sum()):,}")
    slope, roughness = slope_and_roughness(surface, transform)

    flat = np.flatnonzero(mask.ravel())
    rows = (flat // surface.shape[1]).astype(np.int32)
    cols = (flat % surface.shape[1]).astype(np.int32)
    lat = (transform.f + (rows + 0.5) * transform.e).astype(np.float32)
    lon = (transform.c + (cols + 0.5) * transform.a).astype(np.float32)
    tmin = sample_tmin(tmin_grid, tmin_transform, rows, cols, transform)

    lithology = sample_lithology(load_lithology(), rows, cols, transform)
    table = pa.table(
        {
            "lat": lat,
            "lon": lon,
            "elevation_m": surface.ravel()[flat],
            "slope_deg": slope.ravel()[flat],
            "roughness_m": roughness.ravel()[flat],
            "tmin_coldest_month_c": tmin,
            "ice_thickness_m": ice.ravel()[flat],
            "lithology_code": lithology,
        }
    )
    del surface, slope, roughness, ice, mask, tmin_grid
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
    table = table.replace_schema_metadata({k: v.encode() for k, v in meta.items()})
    checks = {
        "atacama": (-24.5, -69.25),
        "death_valley": (36.24, -116.82),
        "iceland": (64.8, -18.0),
        "mcmurdo": (-77.84, 166.67),
    }
    for name, (clat, clon) in checks.items():
        dist = (lat - clat) ** 2 + (lon - clon) ** 2
        i = int(np.argmin(dist))
        code = int(lithology[i])
        tmin_i = table.column("tmin_coldest_month_c")[i].as_py()
        tmin_txt = "null" if tmin_i is None or tmin_i != tmin_i else f"{tmin_i:.1f}"
        print(
            f"check {name}: {lat[i]:.3f},{lon[i]:.3f} "
            f"elev={table.column('elevation_m')[i].as_py():.0f} "
            f"slope={table.column('slope_deg')[i].as_py():.2f} "
            f"rough={table.column('roughness_m')[i].as_py():.1f} "
            f"tmin={tmin_txt} "
            f"ice={table.column('ice_thickness_m')[i].as_py():.0f} "
            f"rock={LITHOLOGY.get(code, '?')}"
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, OUT, compression="zstd")
    (OUT.parent / "columns.json").write_text(json.dumps(meta | {"rows": table.num_rows}, indent=2))
    elapsed = time.perf_counter() - started
    print(f"wrote {OUT} rows={table.num_rows:,} bytes={OUT.stat().st_size:,} in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
