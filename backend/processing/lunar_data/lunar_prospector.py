"""Hydrogen_halfdeg: enteros MSB y referencia ASCII, sin estimar agua o hielo."""

import csv
import hashlib
import math
from pathlib import Path
import struct

from .lola import normalize_coordinates

DOCUMENTATION_URL = "https://pds-geosciences.wustl.edu/missions/lunarp/reduced_special.html"
DATA_URL = "https://pds-geosciences.wustl.edu/missions/lunarp/reduced/"
ROWS, COLUMNS, STEP_DEG = 360, 720, 0.5
QUANTIZATION_TOLERANCE_PPM = 0.100001


def file_manifest(path):
    path = Path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            digest.update(block)
    return {"file_name": path.name, "bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def ascii_record(line):
    fields = next(csv.reader([line.decode("ascii")]))
    if len(fields) != 5:
        raise ValueError("Registro ASCII Hydrogen_halfdeg debe contener cinco columnas")
    bounds = tuple(float(x) for x in fields[:4])
    token = fields[4].strip()
    if token == "**********":
        return bounds, None, token
    value = float(token)
    if not math.isfinite(value):
        raise ValueError("Valor ASCII no finito y no documentado")
    return bounds, value, token


class LunarProspectorHydrogen:
    def __init__(self, binary_path, ascii_path):
        self.binary_path, self.ascii_path = Path(binary_path), Path(ascii_path)
        if self.binary_path.stat().st_size != ROWS * COLUMNS * 2:
            raise ValueError("Hydrogen_halfdeg binario debe contener 720×360 enteros de dos bytes")
        header = []
        with self.ascii_path.open("rb") as stream:
            while True:
                offset = stream.tell()
                line = stream.readline(65537)
                if not line or len(line) > 65536:
                    raise ValueError("Cabecera ASCII ausente o no reconocida")
                if not line.startswith(b"#"):
                    break
                header.append(line)
                if sum(map(len, header)) > 65536:
                    raise ValueError("Cabecera ASCII excesiva")
            header_text = b"".join(header).decode("ascii")
            if not all(text in header_text for text in ("Hydrogen_halfdeg", "259200", "H ppm by weight")):
                raise ValueError("Cabecera no identifica el producto/unidad esperados")
            self.header_bytes, self.record_bytes = offset, len(line)
            if self.record_bytes != 55:
                raise ValueError("Formato ASCII distinto del original validado (55 bytes por registro)")
            if ascii_record(line)[0] != (-90.0, -89.5, -180.0, -179.5):
                raise ValueError("La primera celda no coincide con el orden sur-norte")
            stream.seek(self.header_bytes + (ROWS * COLUMNS - 1) * self.record_bytes)
            if ascii_record(stream.read(self.record_bytes))[0] != (89.5, 90.0, 179.5, 180.0):
                raise ValueError("La última celda no coincide con la geometría global")
        if self.ascii_path.stat().st_size != self.header_bytes + ROWS * COLUMNS * self.record_bytes:
            raise ValueError("Tamaño ASCII no coincide con registros fijos validados")
        self.binary = self.ascii = None

    def __enter__(self):
        if self.binary is not None:
            raise RuntimeError("Lunar Prospector ya abierto")
        self.binary = self.binary_path.open("rb")
        try:
            self.ascii = self.ascii_path.open("rb")
        except Exception:
            self.binary.close()
            self.binary = None
            raise
        return self

    def __exit__(self, *exc):
        for stream in (self.binary, self.ascii):
            if stream is not None:
                stream.close()
        self.binary = self.ascii = None

    def sample(self, latitude_deg, longitude_deg):
        if self.binary is None:
            raise RuntimeError("Abrir Lunar Prospector con with")
        lat, lon = normalize_coordinates(latitude_deg, longitude_deg)
        result = {
            "value": None, "unit": "ppm", "quantity": "estimated_hydrogen_mass_abundance",
            "raw_value": None, "raw_unit": "integer_tenths_ppm", "ascii_reference_value_ppm": None,
            "status": "not_sampled", "available": False, "reason": None,
            "source_ref": "hydrogen_abundance_ppm", "sampling": None,
            "quality": {"uncertainty_ppm": None, "warnings": [
                "model_derived_hydrogen_not_confirmed_water_or_ice",
                "reliability_limited_in_high_thorium_and_rare_earth_regions",
                "half_degree_grid_does_not_establish_effective_resolution",
                "special_product_not_pds_peer_reviewed_archive",
                "body_fixed_frame_realization_not_declared",
                "binary_quantized_ascii_has_more_precision"],
                "validation": "binary_ascii_consistency_not_external_geodetic_validation"},
        }
        if abs(lat) == 90:
            result["reason"] = "exact_pole_not_sampled_longitude_is_degenerate"
            return result
        longitude = (lon + 180) % 360 - 180
        row = min(math.floor((lat + 90) / STEP_DEG), ROWS - 1)
        column = min(math.floor((longitude + 180) / STEP_DEG), COLUMNS - 1)
        index = row * COLUMNS + column
        self.binary.seek(index * 2)
        binary_bytes = self.binary.read(2)
        self.ascii.seek(self.header_bytes + index * self.record_bytes)
        line = self.ascii.read(self.record_bytes)
        if len(binary_bytes) != 2 or len(line) != self.record_bytes:
            raise ValueError("Lectura puntual incompleta")
        raw = struct.unpack(">h", binary_bytes)[0]
        bounds, reference, token = ascii_record(line)
        expected = (-90 + row * STEP_DEG, -90 + (row + 1) * STEP_DEG,
                    -180 + column * STEP_DEG, -180 + (column + 1) * STEP_DEG)
        if bounds != expected:
            raise ValueError("Los límites ASCII no corresponden al píxel binario calculado")
        result.update(raw_value=raw, ascii_reference_value_ppm=reference, ascii_raw_token=token)
        result["sampling"] = {
            "method": "containing_native_pixel_north_east_on_boundary",
            "row": row, "column": column, "index_base": 0, "binary_byte_offset": index * 2,
            "ascii_byte_offset": self.header_bytes + index * self.record_bytes,
            "latitude_bounds_deg": list(bounds[:2]), "longitude_bounds_deg_east_signed": list(bounds[2:]),
            "center_latitude_deg": (bounds[0] + bounds[1]) / 2,
            "center_longitude_deg_east": ((bounds[2] + bounds[3]) / 2) % 360,
            "angular_resolution_deg": STEP_DEG, "binary_scaling_factor": 0.1,
        }
        if reference is None:
            result.update(status="missing", reason="ascii_reserved_asterisks_binary_zero_is_ambiguous")
            return result
        value = raw / 10
        result["binary_ascii_difference_ppm"] = value - reference
        if abs(value - reference) > QUANTIZATION_TOLERANCE_PPM:
            result.update(status="invalid", reason="binary_ascii_disagreement")
        elif value < 0 or reference < 0:
            result.update(status="invalid", reason="negative_hydrogen_estimate")
        else:
            result.update(value=value, status="valid", available=True)
        return result

    def manifest(self):
        return {
            "product_id": "Lunar_Prospector_Hydrogen_halfdeg_December_2001",
            "documentation_url": DOCUMENTATION_URL, "url": DATA_URL + "hydrogenhd.dat",
            "ascii_url": DATA_URL + "hydrogenhd.txt", "release": "2002-01-03",
            "files": [file_manifest(self.binary_path), file_manifest(self.ascii_path)],
            "unit": "ppm", "abundance_basis": "H ppm by weight, model-derived estimate",
            "raster": {"rows": ROWS, "columns": COLUMNS, "dtype": ">i2", "byte_offset": 0,
                       "row_order": "south_to_north", "longitude_interval_deg": [-180, 180],
                       "angular_resolution_deg": STEP_DEG},
            "transformation": {"formula": "signed_int16_raw / 10", "scaling_factor": 0.1},
            "ascii_layout": {"header_bytes": self.header_bytes, "record_bytes": self.record_bytes},
            "missing_policy": "ASCII **********; no universal binary NoData: zero also encodes valid data",
            "negative_policy": "retain raw and ASCII estimates, no physical concentration exported",
            "binary_ascii_tolerance_ppm": QUANTIZATION_TOLERANCE_PPM,
            "limitations": ["not_a_pds_peer_reviewed_archive", "model_dependent_not_water_or_ice",
                            "less_reliable_in_high_thorium_and_rare_earth_regions",
                            "grid_spacing_not_effective_spatial_resolution", "no_per_pixel_uncertainty"],
        }


def validate_binary_against_ascii(binary_path, ascii_path):
    """Contraste completo por dos archivos; sin reutilizar selección ni decoder del lector."""
    count = missing = negative = zero_valid = 0
    largest_difference = 0.0
    special_cells = []
    with Path(binary_path).open("rb") as binary, Path(ascii_path).open("rb") as reference:
        for line in reference:
            if line.startswith(b"#") or not line.strip():
                continue
            fields = line.decode("ascii").split(",")
            if len(fields) != 5:
                raise ValueError("Referencia ASCII inválida")
            row, column = divmod(count, 720)
            bounds = tuple(map(float, fields[:4]))
            if bounds != (row / 2 - 90, (row + 1) / 2 - 90,
                          column / 2 - 180, (column + 1) / 2 - 180):
                raise ValueError("Orientación o geometría ASCII no coincide con el binario")
            encoded = binary.read(2)
            if len(encoded) != 2:
                raise ValueError("Binario truncado durante comparación independiente")
            raw = int.from_bytes(encoded, byteorder="big", signed=True)
            token = fields[4].strip()
            if token == "**********":
                missing += 1
                special_cells.append({"row": row, "column": column, "raw_value": raw,
                                      "ascii_token": token, "kind": "missing"})
            else:
                value = float(token)
                if not math.isfinite(value):
                    raise ValueError("Estimación ASCII no finita")
                difference = abs(raw / 10 - value)
                if difference > 0.100001:
                    raise ValueError("Escala, byte order o valor binario no coincide con ASCII")
                largest_difference = max(largest_difference, difference)
                if value < 0:
                    negative += 1
                    if not any(c["kind"] == "negative" for c in special_cells):
                        special_cells.append({"row": row, "column": column, "raw_value": raw,
                                              "ascii_value_ppm": value, "kind": "negative"})
                elif raw == 0:
                    zero_valid += 1
                    if not any(c["kind"] == "zero_valid" for c in special_cells):
                        special_cells.append({"row": row, "column": column, "raw_value": raw,
                                              "ascii_value_ppm": value, "kind": "zero_valid"})
            count += 1
        if count != 259200 or binary.read(1):
            raise ValueError("Número de celdas ASCII/binario distinto de 259200")
    return {"status": "PASS", "cells_compared": count, "ascii_missing_cells": missing,
            "negative_ascii_estimates": negative, "non_negative_ascii_cells_encoded_zero": zero_valid,
            "max_absolute_binary_ascii_difference_ppm": largest_difference,
            "tolerance_ppm": 0.100001, "special_cells": special_cells,
            "method": "streamed ASCII bounds and values versus sequential int.from_bytes signed big-endian",
            "interpretation": "binary quantization consistency; not independent neutron calibration or external geodetic validation",
            "files": [file_manifest(binary_path), file_manifest(ascii_path)]}
