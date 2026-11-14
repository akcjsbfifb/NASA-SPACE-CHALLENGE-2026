"""Fixtures pequeñas para lectura, más una etiqueta PDS autocontenida y sintética."""

from pathlib import Path
import struct

import pytest

from lunar_data.metadata import FRAME, LolaMetadata


@pytest.fixture
def module_root():
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def metadata_pair(tmp_path):
    result = []
    for variable, product, unit, offset, values in (
        ("elevation", "LDEM_16_FLOAT", "KILOMETER", 1737.4, [-1.25, 0, 1, 2, -2, 3, 4, 5]),
        ("roughness", "LDRM_32_50_FLOAT", "METER", 0, [0.25, 0, 1, 2, 3, 4, 5, 6]),
    ):
        image = tmp_path / f"{variable}.img"
        image.write_bytes(struct.pack("<8f", *values))
        xml = tmp_path / f"{variable}.xml"
        label = tmp_path / f"{variable}.lbl.txt"
        xml.write_text("synthetic fixture; not a scientific source", encoding="utf-8")
        label.write_text("synthetic fixture; not a scientific source", encoding="utf-8")
        result.append(LolaMetadata(
            xml, label, image, product, "synthetic:" + variable, "1.0", "TEST",
            variable, 2, 4, 1 / 90, 2729101.53816, 1, offset, unit,
            1737400, min(values), max(values), (), "TEST_START", "TEST_STOP", (),
        ))
    return result


@pytest.fixture
def pds_product(tmp_path):
    # El tamaño coincide con el producto autorizado. El contenido es sintético;
    # truncate evita construir una matriz completa en RAM.
    image = tmp_path / "ldem_16_float.img"
    with image.open("wb") as stream:
        stream.truncate(2880 * 5760 * 4)
    label = tmp_path / "ldem_16_float.lbl.txt"
    projection = {
        "MAP_PROJECTION_TYPE": '"SIMPLE CYLINDRICAL"', "MAP_RESOLUTION": "16 <pix/deg>",
        "A_AXIS_RADIUS": "1737.4 <km>", "B_AXIS_RADIUS": "1737.4 <km>", "C_AXIS_RADIUS": "1737.4 <km>",
        "POSITIVE_LONGITUDE_DIRECTION": '"EAST"', "CENTER_LATITUDE": "0 <deg>",
        "CENTER_LONGITUDE": "180 <deg>", "LINE_FIRST_PIXEL": "1", "LINE_LAST_PIXEL": "2880",
        "SAMPLE_FIRST_PIXEL": "1", "SAMPLE_LAST_PIXEL": "5760", "MAP_PROJECTION_ROTATION": "0",
        "MAP_SCALE": "1.89521 <km/pix>", "MAXIMUM_LATITUDE": "90 <deg>",
        "MINIMUM_LATITUDE": "-90 <deg>", "WESTERNMOST_LONGITUDE": "0 <deg>",
        "EASTERNMOST_LONGITUDE": "360 <deg>", "LINE_PROJECTION_OFFSET": "1439.5 <pix>",
        "SAMPLE_PROJECTION_OFFSET": "2879.5 <pix>",
        "COORDINATE_SYSTEM_TYPE": '"BODY-FIXED ROTATING"', "COORDINATE_SYSTEM_NAME": f'"{FRAME}"',
    }
    label.write_text('''PDS_VERSION_ID = "PDS3"
PRODUCT_ID = "LDEM_16_FLOAT"
PRODUCT_VERSION_ID = "V3.1"
TARGET_NAME = MOON
OBJECT = UNCOMPRESSED_FILE
FILE_NAME = "LDEM_16_FLOAT.IMG"
RECORD_TYPE = FIXED_LENGTH
FILE_RECORDS = 2880
RECORD_BYTES = 23040
^IMAGE = "LDEM_16_FLOAT.IMG"
OBJECT = IMAGE
NAME = HEIGHT
LINES = 2880
LINE_SAMPLES = 5760
SAMPLE_TYPE = PC_REAL
SAMPLE_BITS = 32
UNIT = KILOMETER
SCALING_FACTOR = 1
OFFSET = 1737.4
MINIMUM = -9.075
MAXIMUM = 10.790
END_OBJECT = IMAGE
END_OBJECT = UNCOMPRESSED_FILE
OBJECT = IMAGE_MAP_PROJECTION
''' + "\n".join(f"{k} = {v}" for k, v in projection.items())
        + "\nEND_OBJECT = IMAGE_MAP_PROJECTION\nEND\n", encoding="utf-8")
    cart_numbers = {
        "west_bounding_coordinate": (0, "deg"), "east_bounding_coordinate": (360, "deg"),
        "north_bounding_coordinate": (90, "deg"), "south_bounding_coordinate": (-90, "deg"),
        "standard_parallel_1": (0, "deg"), "longitude_of_central_meridian": (180, "deg"),
        "pixel_scale_x": (16, "pixel/deg"), "pixel_scale_y": (16, "pixel/deg"),
        "a_axis_radius": (1737.4, "km"), "b_axis_radius": (1737.4, "km"), "c_axis_radius": (1737.4, "km"),
        "pixel_resolution_x": (1.89521, "km/pixel"), "pixel_resolution_y": (1.89521, "km/pixel"),
        "upperleft_corner_x": (-5458204.8, "m"), "upperleft_corner_y": (2729102.4, "m"),
    }
    cart_text = {
        "map_projection_name": "Equirectangular", "latitude_type": "Planetocentric",
        "longitude_direction": "Positive East", "coordinate_system_type": "Body-fixed Rotating",
        "coordinate_system_name": FRAME,
    }
    xml = tmp_path / "ldem_16_float.xml"
    xml.write_text('''<Product_Observational xmlns="http://pds.nasa.gov/pds4/pds/v1"
 xmlns:c="http://pds.nasa.gov/pds4/cart/v1" xmlns:d="http://pds.nasa.gov/pds4/disp/v1"
 xmlns:l="http://pds.nasa.gov/pds4/mission/lro/v1">
<Identification_Area><logical_identifier>urn:nasa:pds:lro_lola_rdr:data_gridded:ldem_16_float</logical_identifier>
<version_id>1.0</version_id></Identification_Area>
<Observation_Area><Target_Identification><name>Moon</name></Target_Identification>
<Time_Coordinates><start_date_time>2009-07-13T17:33:17Z</start_date_time>
<stop_date_time>2016-11-29T05:48:19Z</stop_date_time></Time_Coordinates>
<l:product_version_id>V3.1</l:product_version_id>
<d:horizontal_display_axis>Sample</d:horizontal_display_axis>
<d:horizontal_display_direction>Left to Right</d:horizontal_display_direction>
<d:vertical_display_axis>Line</d:vertical_display_axis>
<d:vertical_display_direction>Top to Bottom</d:vertical_display_direction>
<c:Cartography>'''
        + "".join(f'<c:{k} unit="{u}">{v}</c:{k}>' for k, (v, u) in cart_numbers.items())
        + "".join(f"<c:{k}>{v}</c:{k}>" for k, v in cart_text.items())
        + '''</c:Cartography></Observation_Area>
<File_Area_Observational><File><file_name>ldem_16_float.img</file_name></File>
<Array_2D_Image><offset unit="byte">0</offset><axes>2</axes>
<axis_index_order>Last Index Fastest</axis_index_order>
<Element_Array><data_type>IEEE754LSBSingle</data_type><unit>KILOMETER</unit>
<scaling_factor>1</scaling_factor><value_offset>1737.4</value_offset></Element_Array>
<Axis_Array><axis_name>Line</axis_name><elements>2880</elements><sequence_number>1</sequence_number></Axis_Array>
<Axis_Array><axis_name>Sample</axis_name><elements>5760</elements><sequence_number>2</sequence_number></Axis_Array>
<Object_Statistics><minimum>-9.075</minimum><maximum>10.790</maximum></Object_Statistics>
</Array_2D_Image></File_Area_Observational>
<File_Area_Observational_Supplemental><File><file_name>ldem_16_float.lbl</file_name></File>
</File_Area_Observational_Supplemental></Product_Observational>''', encoding="utf-8")
    return xml, label, image
