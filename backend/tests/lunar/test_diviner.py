from pathlib import Path
import csv
import io
import json
import math

import numpy as np
import pytest

from lunar_data.diviner import DivinerRaster, PRODUCTS
from lunar_data.csv_export import render_csv


@pytest.fixture
def reader_factory(tmp_path, monkeypatch):
    rasterio = pytest.importorskip("rasterio")
    class Dataset:
        width, height, count, dtypes = 46080, 17920, 1, ("float32",)
        crs = rasterio.CRS.from_string("+proj=longlat +R=1737400")
        transform = rasterio.Affine(1/128, 0, -180, 0, -1/128, 70)
        scales, offsets = (1.0,), (0.0,)
        def __init__(self, value): self.value, self.closed, self.windows = value, False, []
        def read(self, band, *, window):
            assert band == 1 and window.width == window.height == 1
            self.windows.append(window)
            return np.array([[self.value]], dtype=np.float32)
        def close(self): self.closed = True
    def factory(variable="rock_abundance", value=0.25):
        code, _ = PRODUCTS[variable]
        xml = tmp_path / f"dghrm_{code}_sam_70s70n_tif.xml"
        cart={"west_bounding_coordinate":-180,"east_bounding_coordinate":180,
              "north_bounding_coordinate":70,"south_bounding_coordinate":-70,
              "pixel_scale_x":128,"pixel_scale_y":128,"a_axis_radius":1737400,
              "b_axis_radius":1737400,"c_axis_radius":1737400,
              "latitude_type":"Planetocentric","longitude_direction":"Positive East",
              "map_projection_name":"Equirectangular"}
        xml.write_text('<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1">'
            '<Identification_Area><logical_identifier>synthetic</logical_identifier></Identification_Area>'
            f'<File_Area_Observational><File><file_name>{xml.stem}.tif</file_name></File>'
            '<Array_2D_Image><Element_Array><data_type>IEEE754LSBSingle</data_type></Element_Array>'
            '<Special_Constants><missing_constant>NaN</missing_constant></Special_Constants>'
            '<Axis_Array><axis_name>Line</axis_name><elements>17920</elements></Axis_Array>'
            '<Axis_Array><axis_name>Sample</axis_name><elements>46080</elements></Axis_Array>'
            '</Array_2D_Image></File_Area_Observational>'+
            ''.join(f'<{k}>{v}</{k}>' for k,v in cart.items())+'</Product_Observational>',encoding='utf-8')
        dataset = Dataset(value)
        monkeypatch.setattr(rasterio, "open", lambda *args, **kwargs: dataset)
        return DivinerRaster(variable, xml, "local.tif"), dataset
    return factory


@pytest.mark.parametrize("lat,lon,row,col", [(0,0,8960,23040),(70,0,0,23040),
    (-70,0,17919,23040),(0,180,8960,0),(0,-180,8960,0), (0,360,8960,23040)])
def test_diviner_native_coordinates(reader_factory,lat,lon,row,col):
    reader,dataset=reader_factory()
    with reader:
        result=reader.sample(lat,lon)
    assert (result["sampling"]["row"],result["sampling"]["column"])==(row,col)
    assert result["value"]==0.25 and result["raw_value"]==0.25
    assert dataset.closed and len(dataset.windows)==1


@pytest.mark.parametrize("lat", [-90,-70.00001,70.00001,90])
def test_outside_does_not_open_or_transfer(reader_factory,lat):
    reader,dataset=reader_factory()
    with reader:
        result=reader.sample(lat,0)
    assert result["value"] is None and result["available"] is False
    assert result["reason"]=="outside_declared_latitude_coverage"
    assert not dataset.windows and reader.dataset is None


@pytest.mark.parametrize("variable,value,unit,status", [
    ("rock_abundance",0,"1","valid"),("rock_abundance",1,"1","valid"),
    ("rock_abundance",1.1,"1","invalid"),("rock_abundance",-1,"1","invalid"),
    ("bolometric_temperature",101.25,"K","valid"),("regolith_temperature",99.5,"K","valid"),
    ("regolith_temperature",-1,"K","invalid"),("rock_abundance",float("nan"),"1","missing"),
    ("bolometric_temperature",float("inf"),"K","missing")])
def test_scales_units_and_nodata(reader_factory,variable,value,unit,status):
    reader,_=reader_factory(variable,value)
    with reader: result=reader.sample(0,0)
    assert result["unit"]==unit and result["status"]==status
    if status=="valid": assert result["value"]==value
    else: assert result["value"] is None
    json.dumps(result,allow_nan=False)


def test_lifecycle_and_invalid_geometry(reader_factory):
    reader,dataset=reader_factory()
    with pytest.raises(RuntimeError): reader.sample(0,0)
    with pytest.raises(ValueError):
        with reader:
            dataset.width=1
            reader.sample(0,0)
    assert dataset.closed


def test_full_csv_is_opt_in_and_matches_all_values(repo_root):
    path=repo_root/"data/moon/lola_measurements.example.json"
    doc=json.loads(path.read_bytes())
    text=render_csv(doc,source_json_file=path.name,source_json_sha256="source",profile="full")
    rows=list(csv.DictReader(io.StringIO(text)))
    assert len(rows[0])==29
    for row,site in zip(rows,doc["sites"]):
        for variable,column in [("rock_abundance","rock_abundance_fraction"),
            ("bolometric_temperature","bolometric_temperature_K"),("regolith_temperature","regolith_temperature_K")]:
            m=site["measurements"][variable]
            assert row[column]==("" if m["value"] is None else str(m["value"]))
            assert row[variable+"_status"]==m["status"]
