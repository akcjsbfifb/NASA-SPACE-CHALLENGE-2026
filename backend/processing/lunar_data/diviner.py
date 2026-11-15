"""Diviner GHRM SAM: celda nativa, con transporte local o HTTP Range acotado."""

import hashlib
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from .http_range import RangeSource
from .lola import normalize_coordinates

PRODUCTS = {
    "rock_abundance": ("ra", "1"),
    "bolometric_temperature": ("tbol", "K"),
    "regolith_temperature": ("treg", "K"),
}
BASE = "https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_ghrm/geotiff/"
SIS = "https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/document/Diviner_RDR_SIS.pdf"
NS = {"p": "http://pds.nasa.gov/pds4/pds/v1", "c": "http://pds.nasa.gov/pds4/cart/v1"}


class DivinerRaster:
    def __init__(self, variable, xml_path, raster=None, budget=None):
        self.variable = variable
        code, self.unit = PRODUCTS[variable]
        self.product = f"dghrm_{code}_sam_70s70n_tif"
        self.xml_path = Path(xml_path)
        self.label_bytes = self.xml_path.read_bytes()
        root = ET.fromstring(self.label_bytes)
        self.lid = root.findtext("p:Identification_Area/p:logical_identifier", namespaces=NS)
        filename = root.findtext("p:File_Area_Observational/p:File/p:file_name", namespaces=NS)
        axes = {n.findtext("p:axis_name", namespaces=NS): int(n.findtext("p:elements", namespaces=NS))
                for n in root.findall(".//p:Array_2D_Image/p:Axis_Array", NS)}
        if filename != self.product + ".tif" or axes != {"Line": 17920, "Sample": 46080}:
            raise ValueError("Producto o geometría PDS Diviner no autorizado")
        if root.findtext(".//p:Element_Array/p:data_type", namespaces=NS) != "IEEE754LSBSingle":
            raise ValueError("Tipo Diviner inesperado")
        if root.findtext(".//p:Special_Constants/p:missing_constant", namespaces=NS) != "NaN":
            raise ValueError("Se requiere la declaración PDS de NaN")
        # El namespace cart tiene versión variable en las etiquetas oficiales.
        def cart(name):
            nodes = [n.text for n in root.iter() if n.tag.rsplit("}", 1)[-1] == name]
            if len(nodes) != 1:
                raise ValueError("Metadato cartográfico ambiguo: " + name)
            return nodes[0]
        checks = {"west_bounding_coordinate": -180, "east_bounding_coordinate": 180,
                  "north_bounding_coordinate": 70, "south_bounding_coordinate": -70,
                  "pixel_scale_x": 128, "pixel_scale_y": 128, "a_axis_radius": 1737400,
                  "b_axis_radius": 1737400, "c_axis_radius": 1737400}
        if any(float(cart(k)) != v for k, v in checks.items()):
            raise ValueError("Cartografía Diviner inesperada")
        if (cart("latitude_type"), cart("longitude_direction"), cart("map_projection_name")) != (
                "Planetocentric", "Positive East", "Equirectangular"):
            raise ValueError("Convención de coordenadas Diviner inesperada")
        if (float(root.findtext(".//p:Element_Array/p:scaling_factor", default="1", namespaces=NS)) != 1 or
                float(root.findtext(".//p:Element_Array/p:value_offset", default="0", namespaces=NS)) != 0):
            raise ValueError("Escala PDS Diviner no documentada")
        self.location = str(raster or BASE + filename)
        self.budget = budget
        self.remote = None
        self.dataset = None
        self.active = False

    def __enter__(self):
        if self.active:
            raise RuntimeError("Diviner ya abierto")
        self.active = True
        return self

    def __exit__(self, *exc):
        if self.dataset is not None:
            self.dataset.close()
            self.dataset = None
        self.active = False

    def _open(self):
        import rasterio
        if self.dataset is not None:
            return
        if self.location.startswith("https://"):
            self.remote = RangeSource(self.location, self.budget)
            ds = rasterio.open(self.remote.name, opener=self.remote.open)
        else:
            ds = rasterio.open(self.location)
        try:
            transform = ds.transform
            if (ds.width, ds.height, ds.count, ds.dtypes) != (46080, 17920, 1, ("float32",)):
                raise ValueError("Geometría TIFF no coincide con PDS")
            if not ds.crs or not ds.crs.is_geographic or not math.isclose(ds.crs.to_dict().get("R", ds.crs.to_dict().get("a", 0)), 1737400):
                # WKT ESRI puede no exportar R en el diccionario PROJ.
                if not ds.crs or '1737400' not in ds.crs.to_wkt() or not ds.crs.is_geographic:
                    raise ValueError("CRS TIFF no es geográfico lunar")
            if any(not math.isclose(a, b, abs_tol=1e-10) for a, b in zip(tuple(transform)[:6], (1/128, 0, -180, 0, -1/128, 70))):
                raise ValueError("Transformación TIFF no coincide con PDS")
            if ds.scales != (1.0,) or ds.offsets != (0.0,):
                raise ValueError("Escala TIFF no documentada; se requiere revisión")
            self.dataset = ds
        except Exception:
            ds.close()
            raise

    def sample(self, latitude_deg, longitude_deg):
        if not self.active:
            raise RuntimeError("Abrir Diviner con with")
        lat, lon = normalize_coordinates(latitude_deg, longitude_deg)
        result = {"value": None, "unit": self.unit, "raw_value": None, "raw_unit": self.unit,
                  "source_ref": self.variable, "status": "not_sampled", "available": False,
                  "reason": None, "sampling": None, "within_declared_latitude_bounds": -70 <= lat <= 70,
                  "quality": {"warnings": ["sam_slope_adjusted_midnight_not_full_thermal_cycle",
                                            "units_from_official_sis_not_element_array",
                                            "body_fixed_frame_realization_not_declared_in_label",
                                            "uncertainty_not_supplied_per_pixel"],
                              "validation": "structural_and_numeric_checks_only"}}
        if abs(lat) > 70:
            result["reason"] = "outside_declared_latitude_coverage"
            return result
        self._open()
        from rasterio.windows import Window
        # Los límites exactos se asignan al píxel interior; el antimeridiano es periódico.
        longitude = (lon + 180) % 360 - 180
        row = min(math.floor((70 - lat) * 128), 17919)
        column = min(math.floor((longitude + 180) * 128), 46079)
        raw = float(self.dataset.read(1, window=Window(column, row, 1, 1))[0, 0])
        result["sampling"] = {"method": "containing_native_pixel_no_interpolation",
                              "row": row, "column": column, "index_base": 0,
                              "center_latitude_deg": 70 - (row + 0.5) / 128,
                              "center_longitude_deg_east": (-180 + (column + 0.5) / 128) % 360,
                              "angular_resolution_deg": 1/128,
                              "nominal_equatorial_pixel_size_m": 236.90117518866782,
                              "scaling_factor": 1.0, "value_offset": 0.0}
        if not math.isfinite(raw):
            result.update(status="missing", reason="pds_nan_or_non_finite_value")
            return result
        result["raw_value"] = raw
        if raw < 0 or (self.unit == "1" and raw > 1):
            result.update(status="invalid", reason="outside_physical_range")
            return result
        result.update(value=raw, available=True, status="valid")
        return result

    def manifest(self):
        source = {"product_id": self.product, "pds_logical_identifier": self.lid,
                  "url": BASE + self.product + ".tif", "unit": self.unit,
                  "unit_authority": {"url": SIS, "section": "11.1, page 69; GHRM"},
                  "element_array_declares_unit": False,
                  "files": [{"file_name": self.xml_path.name, "bytes": len(self.label_bytes),
                             "sha256": hashlib.sha256(self.label_bytes).hexdigest()}],
                  "coverage_latitude_deg": [-70, 70], "angular_resolution_deg": 1/128,
                  "scale": 1.0, "offset": 0.0, "missing_value": "NaN",
                  "georeferencing_note": "PDS projected meters and TIFF geographic degrees describe same equirectangular grid",
                  "body_fixed_frame_realization": "not_declared_in_product_label; no frame conversion applied",
                  "temporal_definition": "slope_adjusted_midnight_not_complete_thermal_cycle"}
        if self.remote is not None:
            source["remote_file"] = self.remote.manifest()
        elif not self.location.startswith("https://"):
            source["local_file_name"] = Path(self.location).name
        return source
