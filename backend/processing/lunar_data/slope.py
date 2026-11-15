"""Pendiente escalar derivada de alturas LDEM, sin lectura ni matrices globales.

Adaptación del método de diferencias centrales de n.x, commit lola-slope
d6daf40f7e12815f3b83418ce4b5bd6928f0acf8. Se conserva su definición matemática;
se reemplazan la construcción global y el parámetro sd no implementado.
"""

import math


def method_description():
    """Metadatos nuevos por llamada para evitar estado compartido mutable."""
    return {
        "id": "central_difference_spherical",
        "version": "1.0.0",
        "formula": "degrees(atan(hypot((east_m-west_m)/(2*dx_m), (south_m-north_m)/(2*dy_m))))",
        "distance_formula": "dy_m=R_m*radians(step_deg); dx_m=dy_m*cos(radians(center_latitude_deg))",
        "height_formula": "raw * scaling_factor * 1000; label radius offset is not added",
        "required_samples": ["center", "north", "south", "east", "west"],
        "longitude_boundary": "periodic",
        "latitude_boundary": "no_result_without_both_latitude_neighbors",
        "missing_policy": "require_all_five_samples_valid_no_substitution",
        "attribution": {
            "original_author": "n.x",
            "original_commit": "d6daf40f7e12815f3b83418ce4b5bd6928f0acf8",
            "original_url": "https://github.com/akcjsbfifb/NASA-SPACE-CHALLENGE-2026/commit/d6daf40f7e12815f3b83418ce4b5bd6928f0acf8",
            "adaptation": "point_sampling_and_validation_in_migrated_lunar_data",
        },
    }


def horizontal_distances(radius_m, angular_step_deg, center_latitude_deg):
    """Pasos entre centros sobre una esfera; no son resolución efectiva del DEM."""
    if not all(math.isfinite(x) for x in (radius_m, angular_step_deg, center_latitude_deg)):
        raise ValueError("La geometría debe ser finita")
    if radius_m <= 0 or not 0 < angular_step_deg <= 180 or abs(center_latitude_deg) >= 90:
        raise ValueError("Geometría esférica inválida o polo degenerado")
    dy_m = radius_m * math.radians(angular_step_deg)
    dx_m = dy_m * math.cos(math.radians(center_latitude_deg))
    if not all(math.isfinite(x) and x > 0 for x in (dx_m, dy_m)):
        raise ValueError("Las distancias deben ser positivas y finitas")
    return dx_m, dy_m


def central_difference_slope(*, center_m, north_m, south_m, east_m, west_m, dx_m, dy_m):
    """Ángulo en grados; cinco alturas válidas en m y dos pasos horizontales en m."""
    if not all(math.isfinite(x) for x in (center_m, north_m, south_m, east_m, west_m)):
        raise ValueError("Se requieren cinco alturas finitas")
    if not all(math.isfinite(x) and x > 0 for x in (dx_m, dy_m)):
        raise ValueError("Las distancias deben ser positivas y finitas")
    gx = (east_m - west_m) / (2 * dx_m)
    gy = (south_m - north_m) / (2 * dy_m)
    if not math.isfinite(gx) or not math.isfinite(gy):
        raise ValueError("Gradiente no finito")
    return math.degrees(math.atan(math.hypot(gx, gy)))
