from dataclasses import replace
import math
import struct

import numpy as np
import pytest

from lunar_data.lola import LolaRaster, normalize_coordinates
from lunar_data.metadata import load_metadata


def test_conversion_and_little_endian_independent_read(metadata_pair):
    elevation, roughness = metadata_pair
    with LolaRaster(elevation) as raster:
        result = raster.sample(45, 45)
        assert result["value"] == -1250
        assert result["sampling"]["row"] == 0
        assert result["sampling"]["column"] == 0
        assert struct.unpack("<f", elevation.image_path.read_bytes()[:4])[0] == result["raw_value"]
        assert raster.sample(45, 135)["value"] == 0  # cero no es NoData
    with LolaRaster(roughness) as raster:
        assert raster.sample(45, 45)["value"] == 0.25  # sin conversión a grados


@pytest.mark.parametrize("lat,lon,row,col", [
    (89, 0, 0, 0), (-89, 359.9, 1, 3), (0, 90, 1, 1),
    (45, -45, 0, 3), (45, 360, 0, 0), (45, 720, 0, 0),
    (45, -360, 0, 0), (math.nextafter(-90, 0), math.nextafter(360, 0), 1, 3),
])
def test_grid_orientation_edges_and_wrapping(metadata_pair, lat, lon, row, col):
    with LolaRaster(metadata_pair[0]) as raster:
        result = raster.sample(lat, lon)
    assert result["sampling"]["row"] == row
    assert result["sampling"]["column"] == col


@pytest.mark.parametrize("lat,lon", [(91, 0), (-91, 0), (float("nan"), 0), (0, float("inf")), (True, 0)])
def test_invalid_coordinates_rejected(lat, lon):
    with pytest.raises(ValueError):
        normalize_coordinates(lat, lon)


@pytest.mark.parametrize("lat", [-90, 90])
def test_exact_poles_have_explicit_policy(metadata_pair, lat):
    with LolaRaster(metadata_pair[0]) as raster:
        result = raster.sample(lat, 20)
    assert result["value"] is None and result["sampling"] is None
    assert result["status"] == "not_sampled" and not result["available"]
    assert "exact_pole" in result["reason"]


@pytest.mark.parametrize("raw,constants,status,reason", [
    (float("nan"), (), "missing", "non_finite_raw_value"),
    (float("inf"), (), "missing", "non_finite_raw_value"),
    (-9999, (-9999,), "missing", "declared_special_constant"),
    (-0.25, (), "invalid", "negative_physical_roughness"),
    (0.1, (0.1,), "missing", "declared_special_constant"),
])
def test_missing_and_invalid_values(metadata_pair, raw, constants, status, reason):
    meta = replace(metadata_pair[1], special_constants=constants)
    with meta.image_path.open("r+b") as stream:
        stream.write(struct.pack("<f", raw))
    with LolaRaster(meta) as raster:
        result = raster.sample(45, 45)
    assert result["status"] == status and result["reason"] == reason
    assert result["value"] is None and result["available"] is False


def test_statistics_are_warning_not_automatic_nodata(metadata_pair):
    meta = replace(metadata_pair[0], minimum=0, maximum=1)
    with LolaRaster(meta) as raster:
        result = raster.sample(45, 45)
    assert result["value"] == -1250
    assert "outside_published_raw_statistics" in result["quality"]["warnings"]


def test_mapping_is_read_only_and_released(metadata_pair):
    meta = metadata_pair[0]
    before = meta.image_path.read_bytes()
    with LolaRaster(meta) as raster:
        assert isinstance(raster._data, np.memmap)
        assert raster._data.mode == "r"
        with pytest.raises(ValueError):
            raster._data[0, 0] = 12
    assert meta.image_path.read_bytes() == before
    meta.image_path.rename(meta.image_path.with_suffix(".released"))


@pytest.mark.local_data
@pytest.mark.parametrize("subdir,product", [("ldem", "ldem_16_float"), ("ldrm", "ldrm_32_50_float")])
def test_real_pixels_against_independent_seek(data_root, subdir, product):
    path = data_root / subdir / f"{product}.xml"
    if not path.exists():
        pytest.skip("IMG locales no incluidos en Git")
    meta = load_metadata(path)
    with LolaRaster(meta) as raster, meta.image_path.open("rb") as stream:
        for lat, lon in [(0, 0), (-85, -10), (89, 359.99), (-89, 120)]:
            result = raster.sample(lat, lon)
            pixel = result["sampling"]
            stream.seek((pixel["row"] * meta.columns + pixel["column"]) * 4)
            assert result["raw_value"] == struct.unpack("<f", stream.read(4))[0]
        first = raster.sample(90 - 0.5 / meta.pixels_per_degree, 0.5 / meta.pixels_per_degree)
        assert first["sampling"]["row"] == 0 and first["sampling"]["column"] == 0
