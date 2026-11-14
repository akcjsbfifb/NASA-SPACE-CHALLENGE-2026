"""Muestreo de la celda nativa que contiene la coordenada, sin interpolación."""

import math

import numpy as np

from .metadata import LolaMetadata, MetadataError
from .slope import central_difference_slope, horizontal_distances, method_description


def normalize_coordinates(latitude_deg, longitude_deg):
    """Entrada planetocéntrica, este positivo; normalización al intervalo [0, 360)."""
    if isinstance(latitude_deg, bool) or isinstance(longitude_deg, bool):
        raise ValueError("Las coordenadas deben ser números, no booleanos")
    latitude, longitude = float(latitude_deg), float(longitude_deg)
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError("Las coordenadas deben ser finitas")
    if not -90 <= latitude <= 90:
        raise ValueError("La latitud debe estar entre -90 y 90 grados")
    # Incluso un negativo diminuto puede redondearse a 360 al aplicar módulo.
    normalized = longitude % 360.0
    if normalized == 360:
        normalized = math.nextafter(360.0, 0.0)
    return latitude, normalized


class LolaRaster:
    """El mapa se abre read-only. Sólo se devuelven escalares, nunca vistas."""

    def __init__(self, metadata: LolaMetadata):
        self.metadata = metadata
        self._data = None

    def __enter__(self):
        if self._data is not None:
            raise RuntimeError("El raster ya está abierto")
        meta = self.metadata
        if meta.image_path.stat().st_size != meta.rows * meta.columns * 4:
            raise MetadataError(f"Cambió el tamaño del raster: {meta.image_path}")
        self._data = np.memmap(
            meta.image_path, dtype="<f4", mode="r", offset=0,
            shape=(meta.rows, meta.columns), order="C",
        )
        return self

    def __exit__(self, *exc):
        # NumPy no tiene close() público; el buffer se cierra una vez consumidos
        # los escalares y sin exponer vistas, para liberar el archivo en Windows.
        if self._data is not None:
            self._data._mmap.close()
            self._data = None

    def _empty_sample(self):
        meta = self.metadata
        warnings = list(meta.warnings)
        result = {
            "status": "not_sampled",
            "available": False,
            "value": None,
            "unit": "m",
            "raw_value": None,
            "raw_unit": meta.raw_unit,
            "reason": None,
            "source_ref": meta.variable,
            "sampling": None,
            "quality": {
                "warnings": warnings,
                "uncertainty_m": None,
                "observation_count": None,
                "direct_observation_or_interpolation": "unknown",
                "validation": "structural_and_numeric_checks_only",
            },
        }
        return result

    def sample(self, latitude_deg, longitude_deg):
        if self._data is None:
            raise RuntimeError("El raster debe abrirse con 'with LolaRaster(...)'")
        lat, lon = normalize_coordinates(latitude_deg, longitude_deg)
        if abs(lat) == 90:
            result = self._empty_sample()
            result["reason"] = "exact_pole_not_sampled_longitude_is_degenerate"
            return result
        meta = self.metadata
        # En un borde se elige la celda hacia el este/sur; min protege redondeo.
        row = min(math.floor((90.0 - lat) * meta.pixels_per_degree), meta.rows - 1)
        col = min(math.floor(lon * meta.pixels_per_degree), meta.columns - 1)
        return self._sample_cell(row, col)

    def _sample_cell(self, row, col):
        """Una lectura escalar; validación y conversión compartidas con pendiente."""
        meta = self.metadata
        result = self._empty_sample()
        warnings = result["quality"]["warnings"]
        center_lat = 90.0 - (row + 0.5) / meta.pixels_per_degree
        center_lon = (col + 0.5) / meta.pixels_per_degree
        result["sampling"] = {
            "method": "containing_native_pixel",
            "index_base": 0,
            "row": row,
            "column": col,
            "center_latitude_deg": center_lat,
            "center_longitude_deg_east": center_lon,
            "angular_resolution_deg": 1.0 / meta.pixels_per_degree,
            "nominal_equatorial_pixel_size_m": meta.map_scale_m,
            "approx_surface_width_at_center_m": (
                meta.reference_radius_m * math.radians(1 / meta.pixels_per_degree)
                * math.cos(math.radians(center_lat))
            ),
        }
        raw = float(self._data[row, col])
        if not math.isfinite(raw):
            result.update(status="missing", reason="non_finite_raw_value")
            return result
        result["raw_value"] = raw
        # Las constantes deben compararse en la representación float32 almacenada.
        if any(raw == float(np.float32(value)) for value in meta.special_constants if math.isfinite(value)):
            result.update(status="missing", reason="declared_special_constant")
            return result
        if meta.variable == "roughness" and raw < 0:
            result.update(status="invalid", reason="negative_physical_roughness")
            return result
        if raw < meta.minimum or raw > meta.maximum:
            warnings.append("outside_published_raw_statistics")
        # Producto LDEM: HEIGHT = DN * SCALE. OFFSET sólo define radio planetario.
        value = raw * meta.scale * (1000.0 if meta.variable == "elevation" else 1.0)
        result.update(status="valid", available=True, value=value)
        return result

    def sample_slope(self, latitude_deg, longitude_deg):
        """Deriva pendiente del LDEM abierto con sólo cinco lecturas escalares.

        Conserva índices, alturas originales y convertidas, y estados de cada
        entrada. No sustituye faltantes ni estima derivadas unilaterales.
        """
        if self.metadata.variable != "elevation":
            raise ValueError("La pendiente requiere el raster LDEM de elevación")
        center = self.sample(latitude_deg, longitude_deg)
        lat, lon = normalize_coordinates(latitude_deg, longitude_deg)
        result = {
            "value": None, "unit": "deg", "raw_value": None, "raw_unit": None,
            "status": "not_sampled", "available": False, "reason": center["reason"],
            "source_ref": "slope", "derived_from": "elevation",
            "requested_coordinates": {"latitude_deg": latitude_deg, "longitude_deg": longitude_deg},
            "normalized_coordinates": {"latitude_deg": lat, "longitude_deg_east": lon},
            "method": method_description(),
            "sampling": None if center["sampling"] is None else dict(center["sampling"]),
            "input_samples": {},
            "quality": {
                "warnings": list(self.metadata.warnings) + [
                    "derived_from_gridded_ldem_not_independent_nasa_slope_product",
                    "spherical_metric_approximation",
                    "longitude_spacing_shrinks_toward_poles",
                    "pixel_spacing_does_not_establish_effective_resolution_or_uncertainty",
                ],
                "uncertainty_deg": None,
                "valid_sample_count": 0,
                "validation": "structural_and_numeric_checks_only",
            },
        }
        if result["sampling"] is None:
            return result
        meta = self.metadata
        sampling = result["sampling"]
        row, col = sampling["row"], sampling["column"]
        dx, dy = horizontal_distances(meta.reference_radius_m, 1 / meta.pixels_per_degree,
                                      sampling["center_latitude_deg"])
        sampling.update(method="central_difference_at_containing_native_pixel",
                        reference_radius_m=meta.reference_radius_m, dx_m=dx, dy_m=dy,
                        east_west_baseline_m=2 * dx, north_south_baseline_m=2 * dy,
                        spacing_ratio_north_south_to_east_west=dy / dx)
        inputs = result["input_samples"]
        inputs["center"] = center
        if row == 0 or row == meta.rows - 1:
            result["reason"] = "latitude_boundary_requires_north_and_south_neighbors"
            result["quality"]["valid_sample_count"] = int(center["available"])
            return result
        for role, r, c in (("north", row - 1, col), ("south", row + 1, col),
                           ("east", row, (col + 1) % meta.columns),
                           ("west", row, (col - 1) % meta.columns)):
            inputs[role] = self._sample_cell(r, c)
        result["quality"]["valid_sample_count"] = sum(item["available"] for item in inputs.values())
        for item in inputs.values():
            for warning in item["quality"]["warnings"]:
                if warning not in result["quality"]["warnings"]:
                    result["quality"]["warnings"].append(warning)
        if not all(item["available"] for item in inputs.values()):
            result.update(status="missing", reason="one_or_more_required_elevations_unavailable")
            return result
        value = central_difference_slope(
            **{role + "_m": item["value"] for role, item in inputs.items()}, dx_m=dx, dy_m=dy)
        result.update(status="valid", available=True, reason=None, value=value)
        return result
