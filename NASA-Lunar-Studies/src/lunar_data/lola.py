"""Muestreo de la celda nativa que contiene la coordenada, sin interpolación."""

import math

import numpy as np

from .metadata import LolaMetadata, MetadataError


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
        self._slope = None

    def __enter__(self):
        meta = self.metadata
        if meta.image_path.stat().st_size != meta.rows * meta.columns * 4:
            raise MetadataError(f"Cambió el tamaño del raster: {meta.image_path}")
        self._data = np.memmap(
            meta.image_path, dtype="<f4", mode="r", offset=0,
            shape=(meta.rows, meta.columns), order="C",
        )
        
        if meta.variable == "elevation":
            self._slope = self._build_slope()

        return self

    def __exit__(self, *exc):
        # NumPy no tiene close() público; el buffer se cierra una vez consumidos
        # los escalares y sin exponer vistas, para liberar el archivo en Windows.
        if self._data is not None:
            self._data._mmap.close()
            self._data = None
            self._slope = None

    def _valid_raw_value(self, raw):
        meta = self.metadata

        if not math.isfinite(raw):
            return False

        if any(raw == float(np.float32(value))
                for value in meta.special_constants
                if math.isfinite(value)):
            return False

        return True

    def _elevation_at(self, row, col):
        raw = float(self._data[row, col])

        if not self._valid_raw_value(raw):
            return None

        return raw * self.metadata.scale * 1000.0

    def _build_slope(self, sd=1):
        if sd <= 1:
            raise ValueError("GRRR")

        meta = self.metadata
        raw = self._data
        valid = self._valid_raw_mask(raw)
        z = raw * (meta.scale * 1000.0)

        rows = meta.rows
        cols = meta.columns

        slope = np.full((rows, cols), np.nan, dtype=np.float32)
        lat = np.radians(90.0 - (np.arange(rows) + 0.5) / meta.pixels_per_degree)
        angular_step = math.radians(1.0 / meta.pixels_per_degree)
        dy = meta.reference_radius_m * angular_step

        dx = (meta.reference_radius_m * angular_step * np.cos(lat))

        east_z = np.roll(z, -1, axis=1)
        west_z = np.roll(z, 1, axis=1)

        east_valid = np.roll(valid, -1, axis=1)
        west_valid = np.roll(valid, 1, axis=1)

        valid_x = valid & east_valid & west_valid

        dz_dx = np.full((rows, cols), np.nan, dtype=np.float32)

        dz_dx[valid_x] = ((east_z[valid_x] - west_z[valid_x]) / (2.0 * np.broadcast_to(dx[:, None], z.shape)[valid_x]))

        dz_dy = np.full((rows, cols), np.nan, dtype=np.float32)

        valid_y = (valid[1:-1, :] & valid[:-2, :] & valid[2:, :])
        dz_dy[1:-1, :][valid_y] = (z[2:, :][valid_y] - z[:-2, :][valid_y]) / (2.0 * dy)

        usable = (valid_x[1:-1, :] & valid_y)
        gradient = np.sqrt(dz_dx[1:-1, :] ** 2 + dz_dy[1:-1, :] ** 2)
        slope[1:-1, :][usable] = np.degrees(np.arctan(gradient[usable]))

        return slope

    def sample(self, latitude_deg, longitude_deg):
        if self._data is None:
            raise RuntimeError("El raster debe abrirse con 'with LolaRaster(...)'")
        lat, lon = normalize_coordinates(latitude_deg, longitude_deg)
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
        if abs(lat) == 90:
            result["reason"] = "exact_pole_not_sampled_longitude_is_degenerate"
            return result
        # En un borde se elige la celda hacia el este/sur. El min sólo protege
        # del redondeo flotante próximo al último borde, nunca de latitudes inválidas.
        row = min(math.floor((90.0 - lat) * meta.pixels_per_degree), meta.rows - 1)
        col = min(math.floor(lon * meta.pixels_per_degree), meta.columns - 1)
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
