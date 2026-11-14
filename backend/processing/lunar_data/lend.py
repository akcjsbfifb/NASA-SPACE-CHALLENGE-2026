"""Observables ALDE LEND: registros binarios de 310 bytes, sin inferir hidrógeno."""

from datetime import datetime
import hashlib
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import pvl

from .lola import normalize_coordinates

NS = {"p": "http://pds.nasa.gov/pds4/pds/v1"}
CHANNEL_OFFSETS = {"STN1": 58, "SETN": 70, "STN2": 82, "STN3": 94, "CSETN": 106}
SIS = "https://pds-geosciences.wustl.edu/lro/lro-l-lend-2-edr-v1/lrolen_0xxx/document/lend_rdr_sis.pdf"


def _utc(text):
    return datetime.fromisoformat(text.rstrip("Z"))


class LendProduct:
    def __init__(self, xml_path):
        self.xml_path = Path(xml_path)
        self.label_path = self.xml_path.with_suffix(".lbl")
        root = ET.parse(self.xml_path).getroot()
        def text(name): return root.findtext(".//p:" + name, namespaces=NS)
        self.product = self.xml_path.stem
        if self.product not in {"lend_rdr_alde_20090915", "lend_rdr_alde_20111211"}:
            raise ValueError("Producto LEND ALDE no autorizado")
        self.lid, self.start, self.stop = text("logical_identifier"), text("start_date_time"), text("stop_date_time")
        self.data_path = self.xml_path.parent / text("file_name")
        if text("file_name") != self.product + ".dat":
            raise ValueError("El DAT no corresponde al producto LEND")
        label = pvl.load(self.label_path)
        if (int(text("records")), int(text("record_length")), int(text("offset"))) != (57600, 310, 0):
            raise ValueError("Estructura PDS4 LEND inesperada")
        if (int(label["FILE_RECORDS"]), int(label["RECORD_BYTES"])) != (57600, 310):
            raise ValueError("PDS3 y PDS4 LEND no coinciden")
        if self.data_path.stat().st_size != 57600 * 310:
            raise ValueError("Tamaño DAT LEND inesperado")
        fields = {node.findtext("p:name", namespaces=NS): node
                  for node in root.findall(".//p:Record_Binary/p:Field_Binary", NS)}
        for name, offset in [("START_UTC_TIME",0),("STOP_UTC_TIME",23)]:
            node=fields[name]
            if (int(node.findtext("p:field_location",namespaces=NS))-1,
                int(node.findtext("p:field_length",namespaces=NS)),
                node.findtext("p:data_type",namespaces=NS)) != (offset,23,"ASCII_String"):
                raise ValueError("Campo temporal LEND inesperado")
        expected = {"LUNARCENTRIC_LATITUDE": 46, "LUNARCENTIC_EAST_LONGITUDE": 50}
        for channel, offset in CHANNEL_OFFSETS.items():
            for suffix, delta in [("EXPOSURE",0),("RATE",4),("ERR",8)]:
                expected[channel+"_"+suffix] = offset + delta
        for name, offset in expected.items():
            node = fields[name]
            if (int(node.findtext("p:field_location",namespaces=NS))-1,
                int(node.findtext("p:field_length",namespaces=NS)),
                node.findtext("p:data_type",namespaces=NS)) != (offset,4,"IEEE754MSBSingle"):
                raise ValueError("Campo LEND no coincide con disposición big-endian: " + name)
            if name.endswith("EXPOSURE") and node.findtext("p:unit",namespaces=NS) != "s":
                raise ValueError("Unidad de exposición LEND inesperada")
            if name.endswith(("RATE","ERR")) and node.find("p:unit",NS) is not None:
                raise ValueError("Nueva unidad de RATE/ERR requiere revisión")
        self.fields = fields
        self.stream = None

    def __enter__(self):
        if self.stream is not None:
            raise RuntimeError("LEND ya abierto")
        self.stream = self.data_path.open("rb")
        return self

    def __exit__(self,*exc):
        if self.stream is not None:
            self.stream.close()
            self.stream = None

    def sample(self, latitude_deg, longitude_deg, channel):
        if self.stream is None:
            raise RuntimeError("Abrir LEND con with")
        if channel not in CHANNEL_OFFSETS:
            raise ValueError("Canal explícito no soportado")
        lat, lon = normalize_coordinates(latitude_deg, longitude_deg)
        result = {"product_id": self.product, "channel": channel,
                  "quantity": "relative_neutron_count_rate",
                  "period": {"start":self.start,"stop":self.stop},
                  "unit":None,"unit_status":"not_declared_in_product_label",
                  "value":None,"raw_value":None,"statistical_error":None,
                  "raw_statistical_error":None,"exposure_s":None,"raw_exposure_s":None,
                  "status":"not_sampled","available":False,"reason":None,
                  "source_ref":self.product,"sampling":None,
                  "quality":{"warnings":["not_hydrogen_water_or_ice_abundance",
                                           "rate_and_error_units_not_declared",
                                           "grid_spacing_not_instrument_resolution",
                                           "body_fixed_frame_realization_not_declared_in_label"],
                             "validation":"structural_and_numeric_checks_only"}}
        if abs(lat) >= 80:
            result["reason"]="outside_declared_latitude_coverage"
            return result
        row=min(math.floor(80-lat),159)
        column=min(math.floor(lon),359)
        index=row*360+column
        self.stream.seek(index*310)
        record=self.stream.read(310)
        if len(record)!=310:
            raise ValueError("Registro LEND incompleto")
        center_lat,center_lon=struct.unpack_from(">2f",record,46)
        if (center_lat,center_lon)!=(79.5-row,column+0.5):
            raise ValueError("Coordenadas del DAT no coinciden con la celda calculada")
        start,stop=record[:23].decode("ascii"),record[23:46].decode("ascii")
        if not _utc(self.start)<=_utc(start)<=_utc(stop)<=_utc(self.stop):
            raise ValueError("Tiempo del registro fuera del período PDS")
        exposure,rate,error=struct.unpack_from(">3f",record,CHANNEL_OFFSETS[channel])
        result["sampling"]={"method":"containing_native_1_degree_cell","row":row,"column":column,
                            "record_index":index,"index_base":0,"byte_offset":index*310,
                            "center_latitude_deg":center_lat,"center_longitude_deg_east":center_lon,
                            "angular_resolution_deg":1,"record_start_utc":start,"record_stop_utc":stop}
        for key,value in [("raw_value",rate),("raw_statistical_error",error),("raw_exposure_s",exposure)]:
            result[key]=value if math.isfinite(value) else None
        if not all(math.isfinite(x) for x in (exposure,rate,error)):
            result.update(status="missing",reason="non_finite_lend_field")
            return result
        result["exposure_s"]=exposure
        if exposure<=0:
            result.update(status="missing",reason="non_positive_exposure_no_supported_measurement")
            return result
        if error<0:
            result.update(status="invalid",reason="negative_statistical_error")
            return result
        if rate<0:
            result["quality"]["warnings"].append("negative_background_subtracted_rate_retained_no_declared_sentinel")
        result.update(value=rate,statistical_error=error,status="valid",available=True)
        return result

    def manifest(self):
        files=[]
        for path in [self.xml_path,self.label_path,self.data_path]:
            digest=hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda:stream.read(1048576),b""):digest.update(block)
            files.append({"file_name":path.name,"bytes":path.stat().st_size,"sha256":digest.hexdigest()})
        return {"product_id":self.product,"pds_logical_identifier":self.lid,
                "period":{"start":self.start,"stop":self.stop},"files":files,
                "coverage_latitude_deg":{"south_exclusive":-80,"north_exclusive":80},
                "angular_resolution_deg":1,"record_length_bytes":310,"byte_order":"big_endian",
                "rate_unit":None,"statistical_error_unit":None,"exposure_unit":"s",
                "unit_policy":"PDS4 structured fields; no RATE/ERR unit inferred from ambiguous legacy SIS",
                "documentation_url":SIS,
                "url":"https://pds-geosciences.wustl.edu/lro/lro-l-lend-2-edr-v1/lrolen_0xxx/data/"+
                      self.product[-8:-4]+"/"+self.product[-8:]+"/"+self.product+".dat",
                "limitations":["indirect_neutron_observable_not_abundance", "no_period_or_sensor_combination",
                               "legacy_sis_exposure_unit_text_conflicts_with_seconds_description_xml_used"]}


class LendCollection:
    """Agrupa observaciones sin combinarlas; mantiene la clave histórica del registro."""
    def __init__(self, selections):
        self.selections=selections

    def sample(self, lat, lon):
        observations=[product.sample(lat,lon,channel) for product,channels in self.selections for channel in channels]
        return {"value":None,"unit":None,"available":False,"kind":"collection",
                "has_available_observations":any(x["available"] for x in observations),
                "status":"not_sampled","reason":"no_single_scalar_periods_and_channels_kept_in_observations",
                "source_ref":"lend_neutron_indicator","quantity":"collection_of_relative_neutron_count_rates",
                "observations":observations}

    def manifest(self):
        return {"kind":"collection","products":[product.product for product,_ in self.selections],
                "selections":[{"product":product.product,"channels":channels} for product,channels in self.selections],
                "combination_applied":False}

    def additional_sources(self):
        return {product.product:product.manifest() for product,_ in self.selections}
