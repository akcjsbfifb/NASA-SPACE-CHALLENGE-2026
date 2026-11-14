"""Pruebas analíticas, de acceso puntual y contraste binario independiente."""

from dataclasses import replace
import json
import math
import struct

import numpy as np
import pytest

from lunar_data.export import build_document, read_json, write_document
from lunar_data.lola import LolaRaster
from lunar_data.metadata import load_metadata
from lunar_data.slope import central_difference_slope, horizontal_distances


@pytest.fixture
def elevation_grid(metadata_pair):
    def make(values=None, **changes):
        values = np.full((6, 12), -2, dtype="<f4") if values is None else np.asarray(values, dtype="<f4")
        meta = replace(metadata_pair[0], rows=6, columns=12, pixels_per_degree=1 / 30,
                       minimum=-100, maximum=100, **changes)
        meta.image_path.write_bytes(values.tobytes())
        return meta
    return make


@pytest.mark.parametrize("gx,gy", [(0, 0), (1, 0), (0, -1), (0.3, 0.4), (-1, -1)])
def test_analytic_gradients(gx, gy):
    dx, dy, center = 20, 30, -1500
    result = central_difference_slope(center_m=center, north_m=center - gy * dy,
        south_m=center + gy * dy, east_m=center + gx * dx, west_m=center - gx * dx,
        dx_m=dx, dy_m=dy)
    expected = math.atan(math.sqrt(gx * gx + gy * gy)) * 180 / math.pi
    assert result == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize("field,value", [("center_m", float("nan")), ("north_m", float("inf")),
    ("east_m", -float("inf")), ("dx_m", 0), ("dy_m", -1), ("dx_m", float("nan"))])
def test_pure_function_rejects_invalid_inputs(field, value):
    values = dict(center_m=0, north_m=0, south_m=0, east_m=0, west_m=0, dx_m=1, dy_m=1)
    values[field] = value
    with pytest.raises(ValueError):
        central_difference_slope(**values)


@pytest.mark.parametrize("latitude", [0, 45, -85, 89.9])
def test_spherical_distances(latitude):
    dx, dy = horizontal_distances(1737400, 1 / 16, latitude)
    expected_dy = 2 * math.pi * 1737400 / (360 * 16)
    assert dy == pytest.approx(expected_dy)
    assert dx == pytest.approx(expected_dy * math.cos(latitude * math.pi / 180))


@pytest.mark.parametrize("geometry", [(0, 1, 0), (1, 0, 0), (1, 1, 90),
    (1, 1, -90), (1, 1, 91), (float("inf"), 1, 0), (1, 1, float("nan"))])
def test_invalid_geometry(geometry):
    with pytest.raises(ValueError):
        horizontal_distances(*geometry)


def test_flat_negative_elevation_is_valid(elevation_grid):
    with LolaRaster(elevation_grid()) as raster:
        result = raster.sample_slope(-1, 1)
    assert result["value"] == 0
    assert result["status"] == "valid" and result["available"]
    assert result["raw_value"] is None and result["raw_unit"] is None
    assert result["quality"]["valid_sample_count"] == 5
    assert all(sample["value"] == -2000 for sample in result["input_samples"].values())


def test_kilometer_conversion_scale_and_neighbor_positions(elevation_grid):
    data = np.full((6, 12), -2, dtype="<f4")
    data[3, 1], data[3, 11] = -1, -3
    data[2, 0], data[4, 0] = -4, 0
    with LolaRaster(elevation_grid(data, scale=0.25)) as raster:
        result = raster.sample_slope(-1, 0)
    samples = result["input_samples"]
    assert samples["east"]["raw_value"] == -1
    assert samples["east"]["value"] == -250
    assert samples["north"]["value"] == -1000
    assert samples["west"]["sampling"]["column"] == 11
    assert samples["south"]["sampling"]["row"] == 4
    step = 1737400 * math.pi / 6
    gx = 500 / (2 * step * math.cos(-15 * math.pi / 180))
    gy = 1000 / (2 * step)
    expected = math.atan(math.sqrt(gx**2 + gy**2)) * 180 / math.pi
    assert result["value"] == pytest.approx(expected, abs=1e-12)
    assert result["sampling"]["dx_m"] == pytest.approx(step * math.cos(math.pi / 12))


@pytest.mark.parametrize("longitude,column", [(0, 0), (360, 0), (-360, 0),
    (720, 0), (-1, 11), (359.9, 11)])
def test_periodic_longitude(elevation_grid, longitude, column):
    with LolaRaster(elevation_grid()) as raster:
        result = raster.sample_slope(-1, longitude)
    assert result["sampling"]["column"] == column
    assert result["input_samples"]["east"]["sampling"]["column"] == (column + 1) % 12
    assert result["input_samples"]["west"]["sampling"]["column"] == (column - 1) % 12
    assert result["requested_coordinates"]["longitude_deg"] == longitude


@pytest.mark.parametrize("latitude,pole", [(90, True), (-90, True), (89.9, False), (-89.9, False)])
def test_poles_and_latitude_boundaries(elevation_grid, latitude, pole):
    with LolaRaster(elevation_grid()) as raster:
        result = raster.sample_slope(latitude, 0)
    assert result["status"] == "not_sampled" and not result["available"]
    assert result["value"] is None
    assert (result["sampling"] is None) == pole
    assert ("exact_pole" if pole else "latitude_boundary") in result["reason"]


@pytest.mark.parametrize("position", [(3, 0), (2, 0), (4, 0), (3, 1), (3, 11)])
@pytest.mark.parametrize("value,constants", [(float("nan"), ()), (float("inf"), ()),
    (-9999, (-9999,)), (0.1, (0.1,))])
def test_missing_center_or_any_neighbor(elevation_grid, position, value, constants):
    data = np.full((6, 12), -2, dtype="<f4")
    data[position] = value
    with LolaRaster(elevation_grid(data, special_constants=constants)) as raster:
        result = raster.sample_slope(-1, 0)
    assert result["status"] == "missing" and not result["available"]
    assert result["value"] is None
    assert result["quality"]["valid_sample_count"] == 4
    # Ni NaN ni infinitos llegan al JSON, incluso en las entradas auxiliares.
    json.dumps(result, allow_nan=False)


def test_only_five_scalar_reads_and_no_calculation_on_open(elevation_grid, monkeypatch):
    import lunar_data.lola as module
    meta = elevation_grid()
    original = module.central_difference_slope
    def forbidden(**kwargs):
        raise AssertionError("No debe calcular pendiente al abrir")
    monkeypatch.setattr(module, "central_difference_slope", forbidden)
    with LolaRaster(meta) as raster:
        mapped = raster._data
        assert isinstance(mapped, np.memmap) and mapped.mode == "r"
        monkeypatch.setattr(module, "central_difference_slope", original)
        reads = []
        class ScalarOnly:
            def __getitem__(self, index):
                assert isinstance(index, tuple) and len(index) == 2
                assert all(isinstance(i, int) for i in index)
                reads.append(index)
                return mapped[index]
            def __array__(self, *args, **kwargs):
                raise AssertionError("No se permite materializar el raster")
        raster._data = ScalarOnly()
        try:
            assert raster.sample_slope(-1, 0)["value"] == 0
        finally:
            raster._data = mapped
        assert reads == [(3, 0), (2, 0), (4, 0), (3, 1), (3, 11)]
    assert mapped._mmap.closed


def test_resources_released_on_error_and_reentry_rejected(elevation_grid, monkeypatch):
    import lunar_data.lola as module
    meta = elevation_grid()
    before = meta.image_path.read_bytes()
    def fail(**kwargs):
        raise ValueError("injected failure")
    monkeypatch.setattr(module, "central_difference_slope", fail)
    raster = LolaRaster(meta)
    with pytest.raises(ValueError, match="injected"):
        with raster:
            mapped = raster._data
            with pytest.raises(RuntimeError, match="ya está abierto"):
                raster.__enter__()
            raster.sample_slope(-1, 0)
    assert raster._data is None and mapped._mmap.closed
    assert meta.image_path.read_bytes() == before
    meta.image_path.rename(meta.image_path.with_suffix(".released"))
    with pytest.raises(RuntimeError):
        raster.sample_slope(-1, 0)


def test_roughness_is_not_a_slope_source(metadata_pair):
    with LolaRaster(metadata_pair[1]) as raster:
        with pytest.raises(ValueError, match="LDEM"):
            raster.sample_slope(0, 0)


def test_export_provenance_and_reproducibility(elevation_grid, metadata_pair, registry_path, tmp_path):
    meta = elevation_grid()
    sites = [{"id": "synthetic", "is_example": True, "latitude_deg": -1, "longitude_deg": -360}]
    first = build_document([meta, metadata_pair[1]], sites, read_json(registry_path))
    second = build_document([meta, metadata_pair[1]], sites, read_json(registry_path))
    assert first == second
    slope = first["sites"][0]["measurements"]["slope"]
    assert slope["value"] == 0 and slope["implemented"] is True
    assert slope["requested_coordinates"]["longitude_deg"] == -360
    assert slope["normalized_coordinates"]["longitude_deg_east"] == 0
    assert slope["used_in_similarity"] is None
    source = first["sources"][slope["source_ref"]]
    assert source["derived_from"] == ["elevation"]
    assert source["method"] == slope["method"]
    assert source["method"]["attribution"]["original_commit"] == "d6daf40f7e12815f3b83418ce4b5bd6928f0acf8"
    write_document(first, tmp_path / "one.json")
    write_document(second, tmp_path / "two.json")
    assert (tmp_path / "one.json").read_bytes() == (tmp_path / "two.json").read_bytes()


@pytest.mark.local_data
@pytest.mark.parametrize("lat,lon", [(0, 0), (-85, -10)])
def test_real_slope_independent_five_binary_reads(data_root, repo_root, lat, lon):
    xml = data_root / "ldem/ldem_16_float.xml"
    if not xml.exists():
        pytest.skip("IMG locales no incluidos en Git")
    meta = load_metadata(xml)
    row = int((90 - lat) * meta.pixels_per_degree)
    col = int((lon % 360) * meta.pixels_per_degree)
    positions = {"center": (row, col), "north": (row-1, col), "south": (row+1, col),
                 "east": (row, (col+1) % meta.columns), "west": (row, (col-1) % meta.columns)}
    raw = {}
    with meta.image_path.open("rb") as stream:
        for role, (r, c) in positions.items():
            stream.seek(4 * (r * meta.columns + c))
            raw[role] = struct.unpack("<f", stream.read(4))[0]
    # Oráculo independiente: sin central_difference_slope ni horizontal_distances.
    height = {role: value * meta.scale * 1000 for role, value in raw.items()}
    phi = (90 - (row + 0.5) / meta.pixels_per_degree) * math.pi / 180
    ns_span = 2 * meta.reference_radius_m * math.pi / (180 * meta.pixels_per_degree)
    ew_span = ns_span * math.cos(phi)
    gx = (height["east"] - height["west"]) / ew_span
    gy = (height["south"] - height["north"]) / ns_span
    expected = math.atan(math.sqrt(gx * gx + gy * gy)) * 180 / math.pi
    historical = read_json(repo_root / "NASA-Lunar-Studies/examples/lola_measurements.example.json")
    site_index = 0 if lat == 0 else 1
    with LolaRaster(meta) as raster:
        result = raster.sample_slope(lat, lon)
        # Igualdad completa de la medición previa: valores, centros, unidades y calidad.
        measured_height = raster.sample(lat, lon)
    old = historical["sites"][site_index]["measurements"]["elevation"]
    for key in measured_height:
        assert measured_height[key] == old[key]
    rough_meta = load_metadata(data_root / "ldrm/ldrm_32_50_float.xml")
    with LolaRaster(rough_meta) as raster:
        roughness = raster.sample(lat, lon)
    old_roughness = historical["sites"][site_index]["measurements"]["roughness"]
    for key in roughness:
        assert roughness[key] == old_roughness[key]
    assert result["value"] == pytest.approx(expected, abs=1e-12)
    assert result["sampling"]["east_west_baseline_m"] == pytest.approx(ew_span)
    for role, sample in result["input_samples"].items():
        assert sample["raw_value"] == raw[role]
        assert sample["value"] == height[role]
        assert (sample["sampling"]["row"], sample["sampling"]["column"]) == positions[role]
