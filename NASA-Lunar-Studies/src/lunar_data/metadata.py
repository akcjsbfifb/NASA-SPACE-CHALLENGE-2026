"""Lector deliberadamente limitado a los dos productos LOLA float aprobados."""

from dataclasses import dataclass
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import pvl

NS = {
    "p": "http://pds.nasa.gov/pds4/pds/v1",
    "c": "http://pds.nasa.gov/pds4/cart/v1",
    "d": "http://pds.nasa.gov/pds4/disp/v1",
    "l": "http://pds.nasa.gov/pds4/mission/lro/v1",
}
FRAME = "MEAN EARTH/POLAR AXIS OF DE421"
SOURCE_BASE = (
    "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/"
    "lrolol_1xxx/data/lola_gdr/cylindrical/float_img/"
)
PRODUCTS = {
    "LDEM_16_FLOAT": ("elevation", "KILOMETER", "HEIGHT", 16),
    "LDRM_32_50_FLOAT": ("roughness", "METER", "ROUGHNESS", 32),
}


class MetadataError(ValueError):
    """Archivo o geometría no compatible con esta versión del extractor."""


@dataclass(frozen=True)
class LolaMetadata:
    xml_path: Path
    label_path: Path
    image_path: Path
    product_id: str
    logical_identifier: str
    label_version: str
    product_version: str
    variable: str
    rows: int
    columns: int
    pixels_per_degree: float
    map_scale_m: float
    scale: float
    value_offset: float
    raw_unit: str
    reference_radius_m: float
    minimum: float
    maximum: float
    special_constants: tuple[float, ...]
    observation_start: str
    observation_stop: str
    warnings: tuple[str, ...]


def _text(node, path):
    value = node.findtext(path, namespaces=NS)
    if value is None or not value.strip():
        raise MetadataError(f"Falta metadato obligatorio: {path}")
    return value.strip()


def _number(node, path, unit=None):
    element = node.find(path, NS)
    if element is None or (unit is not None and element.get("unit") != unit):
        raise MetadataError(f"Falta metadato o unidad inesperada: {path} ({unit})")
    value = float(_text(node, path))
    if not math.isfinite(value):
        raise MetadataError(f"Metadato no finito: {path}")
    return value


def _equal(actual, expected, field):
    if isinstance(expected, (int, float)):
        matches = math.isfinite(float(actual)) and math.isclose(
            float(actual), expected, rel_tol=1e-10, abs_tol=1e-10
        )
    else:
        matches = actual == expected
    if not matches:
        raise MetadataError(f"Metadato incompatible en {field}: {actual!r}; esperado {expected!r}")


def _pds_number(value, unit=None):
    if unit is not None and getattr(value, "units", None) != unit:
        raise MetadataError(f"Unidad PDS3 incompatible: {value!r}; esperado {unit}")
    return float(getattr(value, "value", value))


def _local_reference(directory, name, label=False):
    # Sólo nombres de archivos vecinos: nunca navegar rutas incluidas en etiquetas.
    if not name or any(char in name for char in ("/", "\\", ":")) or name in (".", ".."):
        raise MetadataError(f"Referencia no local: {name!r}")
    candidates = [name]
    if label and name.lower().endswith(".lbl"):
        candidates.append(name + ".txt")
    for candidate in candidates:
        matches = [p for p in directory.iterdir() if p.name.casefold() == candidate.casefold()]
        if len(matches) > 1:
            raise MetadataError(f"Referencia ambigua: {candidate}")
        if matches:
            path = matches[0].resolve()
            if not path.is_file() or path.parent != directory.resolve():
                raise MetadataError(f"Referencia fuera del directorio de datos: {candidate}")
            return path
    raise MetadataError(f"No existe archivo referenciado: {directory / name}")


def load_metadata(xml_path):
    """Contrasta PDS4/PDS3; no aplica automáticamente escala ni value_offset."""
    try:
        return _load_metadata(Path(xml_path).resolve())
    except MetadataError:
        raise
    except (ET.ParseError, KeyError, TypeError, ValueError, OSError) as exc:
        raise MetadataError(f"No se pudo interpretar {xml_path}: {exc}") from exc


def _load_metadata(xml_path):
    root = ET.parse(xml_path).getroot()
    _equal(root.tag, f"{{{NS['p']}}}Product_Observational", "tipo PDS4")
    _equal(_text(root, ".//p:Target_Identification/p:name"), "Moon", "cuerpo")
    area = root.find("p:File_Area_Observational", NS)
    arrays = root.findall("p:File_Area_Observational/p:Array_2D_Image", NS)
    if area is None or len(arrays) != 1:
        raise MetadataError("Se requiere exactamente un Array_2D_Image")
    array = arrays[0]
    image_name = _text(area, "p:File/p:file_name")
    image_path = _local_reference(xml_path.parent, image_name)
    label_name = _text(root, "p:File_Area_Observational_Supplemental/p:File/p:file_name")
    label_path = _local_reference(xml_path.parent, label_name, label=True)
    label = pvl.loads(label_path.read_text(encoding="utf-8-sig"))
    product_id = str(label["PRODUCT_ID"])
    if product_id not in PRODUCTS:
        raise MetadataError(f"Producto no soportado: {product_id}")
    variable, unit, image_kind, ppd = PRODUCTS[product_id]
    lid = _text(root, "p:Identification_Area/p:logical_identifier")
    _equal(lid, "urn:nasa:pds:lro_lola_rdr:data_gridded:" + product_id.lower(), "LID")
    _equal(label["PDS_VERSION_ID"], "PDS3", "versión PDS3")
    _equal(label["TARGET_NAME"], "MOON", "cuerpo PDS3")
    data = label["UNCOMPRESSED_FILE"]
    image = data["IMAGE"]
    projection = label["IMAGE_MAP_PROJECTION"]
    for field in ("FILE_NAME", "^IMAGE"):
        _equal(str(data[field]).casefold(), image_name.casefold(), field)
    _equal(data["RECORD_TYPE"], "FIXED_LENGTH", "tipo de registro")
    _equal(image["NAME"], image_kind, "magnitud")
    _equal(image["SAMPLE_TYPE"], "PC_REAL", "orden de bytes")
    _equal(image["SAMPLE_BITS"], 32, "bits")
    _equal(image["UNIT"], unit, "unidad PDS3")
    _equal(_text(array, "p:Element_Array/p:unit"), unit, "unidad PDS4")
    _equal(_text(array, "p:Element_Array/p:data_type"), "IEEE754LSBSingle", "tipo PDS4")
    _equal(_text(array, "p:axis_index_order"), "Last Index Fastest", "orden de ejes")
    _equal(_number(array, "p:offset", "byte"), 0, "offset binario")
    _equal(_number(array, "p:axes"), 2, "cantidad de ejes")
    axes = array.findall("p:Axis_Array", NS)
    _equal(len(axes), 2, "ejes")
    dimensions = []
    for index, (axis, name) in enumerate(zip(axes, ("Line", "Sample")), 1):
        _equal(_text(axis, "p:axis_name"), name, "nombre del eje")
        _equal(_number(axis, "p:sequence_number"), index, "secuencia del eje")
        size = _number(axis, "p:elements")
        _equal(size, int(size), "dimensión entera")
        dimensions.append(int(size))
    rows, columns = dimensions
    _equal(rows, 180 * ppd, "filas")
    _equal(columns, 360 * ppd, "columnas")
    for field, expected in (("LINES", rows), ("LINE_SAMPLES", columns)):
        _equal(image[field], expected, field)
    _equal(data["FILE_RECORDS"], rows, "registros")
    _equal(data["RECORD_BYTES"], columns * 4, "bytes por registro")
    _equal(image_path.stat().st_size, rows * columns * 4, "tamaño IMG")

    cart = root.find(".//c:Cartography", NS)
    if cart is None:
        raise MetadataError("Falta Cartography")
    for tag, expected in (
        ("map_projection_name", "Equirectangular"),
        ("latitude_type", "Planetocentric"),
        ("longitude_direction", "Positive East"),
        ("coordinate_system_type", "Body-fixed Rotating"),
        ("coordinate_system_name", FRAME),
    ):
        _equal(_text(cart, f".//c:{tag}"), expected, tag)
    for tag, expected, tag_unit in (
        ("west_bounding_coordinate", 0, "deg"), ("east_bounding_coordinate", 360, "deg"),
        ("north_bounding_coordinate", 90, "deg"), ("south_bounding_coordinate", -90, "deg"),
        ("standard_parallel_1", 0, "deg"), ("longitude_of_central_meridian", 180, "deg"),
        ("pixel_scale_x", ppd, "pixel/deg"), ("pixel_scale_y", ppd, "pixel/deg"),
        ("a_axis_radius", 1737.4, "km"), ("b_axis_radius", 1737.4, "km"),
        ("c_axis_radius", 1737.4, "km"),
    ):
        _equal(_number(cart, f".//c:{tag}", tag_unit), expected, tag)
    _equal(projection["MAP_PROJECTION_TYPE"], "SIMPLE CYLINDRICAL", "proyección PDS3")
    _equal(projection["POSITIVE_LONGITUDE_DIRECTION"], "EAST", "sentido de longitud")
    _equal(projection["COORDINATE_SYSTEM_TYPE"], "BODY-FIXED ROTATING", "tipo de marco")
    _equal(projection["COORDINATE_SYSTEM_NAME"], FRAME, "marco PDS3")
    for field, expected, pds_unit in (
        ("MAP_RESOLUTION", ppd, "pix/deg"),
        ("CENTER_LATITUDE", 0, "deg"), ("CENTER_LONGITUDE", 180, "deg"),
        ("MAXIMUM_LATITUDE", 90, "deg"), ("MINIMUM_LATITUDE", -90, "deg"),
        ("WESTERNMOST_LONGITUDE", 0, "deg"), ("EASTERNMOST_LONGITUDE", 360, "deg"),
        ("A_AXIS_RADIUS", 1737.4, "km"), ("B_AXIS_RADIUS", 1737.4, "km"),
        ("C_AXIS_RADIUS", 1737.4, "km"),
        ("LINE_PROJECTION_OFFSET", rows / 2 - 0.5, "pix"),
        ("SAMPLE_PROJECTION_OFFSET", columns / 2 - 0.5, "pix"),
    ):
        _equal(_pds_number(projection[field], pds_unit), expected, field)
    _equal(projection["MAP_PROJECTION_ROTATION"], 0, "rotación")
    for field, expected in (
        ("LINE_FIRST_PIXEL", 1), ("LINE_LAST_PIXEL", rows),
        ("SAMPLE_FIRST_PIXEL", 1), ("SAMPLE_LAST_PIXEL", columns),
    ):
        _equal(projection[field], expected, field)
    for tag, expected in (
        ("horizontal_display_axis", "Sample"), ("horizontal_display_direction", "Left to Right"),
        ("vertical_display_axis", "Line"), ("vertical_display_direction", "Top to Bottom"),
    ):
        _equal(_text(root, f".//d:{tag}"), expected, tag)
    map_scale = _pds_number(projection["MAP_SCALE"], "km/pix")
    if map_scale <= 0:
        raise MetadataError("MAP_SCALE debe ser positivo")
    for axis in ("x", "y"):
        _equal(_number(cart, f".//c:pixel_resolution_{axis}", "km/pixel"), map_scale, "escala métrica")
    # Los valores métricos LDEM están redondeados; la indexación usa grados exactos.
    _equal(_number(cart, ".//c:upperleft_corner_x", "m"), -columns * map_scale * 500, "origen x")
    _equal(_number(cart, ".//c:upperleft_corner_y", "m"), rows * map_scale * 500, "origen y")
    scale_text = array.findtext("p:Element_Array/p:scaling_factor", namespaces=NS)
    offset_text = array.findtext("p:Element_Array/p:value_offset", namespaces=NS)
    scale = float(scale_text) if scale_text is not None else 1.0
    offset = float(offset_text) if offset_text is not None else 0.0
    _equal(scale, float(image.get("SCALING_FACTOR", 1)), "factor de escala")
    _equal(offset, float(image.get("OFFSET", 0)), "offset de valor")
    _equal(scale, 1, "escala de estos productos")
    _equal(offset, 1737.4 if variable == "elevation" else 0, "offset de estos productos")
    product_version = _text(root, ".//l:product_version_id")
    _equal(label["PRODUCT_VERSION_ID"], product_version, "versión científica")
    minimum = _number(array, "p:Object_Statistics/p:minimum")
    maximum = _number(array, "p:Object_Statistics/p:maximum")
    _equal(float(image["MINIMUM"]), minimum, "mínimo")
    _equal(float(image["MAXIMUM"]), maximum, "máximo")
    if minimum > maximum:
        raise MetadataError("Rango estadístico invertido")
    constants = []
    for element in array.findall("p:Special_Constants/*", NS):
        if element.tag.rsplit("}", 1)[-1].endswith("_constant"):
            constants.append(float(element.text))
    for key, value in image.items():
        if key in {"MISSING_CONSTANT", "INVALID_CONSTANT", "NULL", "CORE_NULL"}:
            constants.append(float(value))
    warnings = []
    if label_path.name.casefold() != label_name.casefold():
        warnings.append("pds3_label_resolved_as_lbl_txt")
    if not constants:
        warnings.append("no_declared_special_constants")
    if variable == "roughness":
        warnings.extend(("ldrm_unit_text_conflict_resolved_as_meters", "ldrc_observation_count_unavailable"))
    else:
        warnings.append("ldem_reference_sphere_offset_not_added_to_height")
    return LolaMetadata(
        xml_path, label_path, image_path, product_id, lid,
        _text(root, "p:Identification_Area/p:version_id"), product_version,
        variable, rows, columns, ppd, map_scale * 1000, scale, offset, unit, 1737400.0,
        minimum, maximum, tuple(constants),
        _text(root, ".//p:Time_Coordinates/p:start_date_time"),
        _text(root, ".//p:Time_Coordinates/p:stop_date_time"), tuple(warnings),
    )
