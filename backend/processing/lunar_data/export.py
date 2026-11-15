"""Contrato extensible y salida determinista: sin puntajes ni confianza inventada."""

from contextlib import ExitStack
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform

from . import __version__
from .lola import LolaRaster, normalize_coordinates
from .metadata import FRAME, SOURCE_BASE
from .slope import method_description


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _file_manifest(path):
    return {"file_name": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def read_json(path):
    def invalid_constant(value):
        raise ValueError(f"Constante no permitida en JSON: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), parse_constant=invalid_constant)


def validate_sites(sites):
    if not isinstance(sites, list) or not sites:
        raise ValueError("Se requiere una lista no vacía de sitios")
    seen = set()
    for site in sites:
        if not isinstance(site, dict):
            raise ValueError("Cada sitio debe ser un objeto")
        if not isinstance(site.get("id"), str) or not site["id"].strip() or site["id"] in seen:
            raise ValueError("Cada sitio debe tener un id no vacío y único")
        seen.add(site["id"])
        if not isinstance(site.get("is_example"), bool):
            raise ValueError("Cada sitio debe declarar is_example: true/false")
        for key in ("latitude_deg", "longitude_deg"):
            if isinstance(site.get(key), bool) or not isinstance(site.get(key), (int, float)):
                raise ValueError(f"{key} debe ser un número")
        normalize_coordinates(site["latitude_deg"], site["longitude_deg"])


def validate_registry(registry):
    if not isinstance(registry, dict) or registry.get("schema_version") != "1.0.0":
        raise ValueError("Registro de variables incompatible")
    variables = registry.get("variables")
    if not isinstance(variables, list) or not variables:
        raise ValueError("Falta lista de variables")
    ids = [item["id"] for item in variables]
    if len(set(ids)) != len(ids):
        raise ValueError("Identificadores de variable duplicados")
    implemented = {item["id"] for item in variables if item.get("implemented") is True}
    required = {"elevation", "roughness", "slope"}
    supported = required | {"rock_abundance", "bolometric_temperature", "regolith_temperature", "hydrogen_abundance_ppm"}
    if not required <= implemented <= supported:
        raise ValueError("Registro reclama procesadores no implementados")
    for item in variables:
        if not isinstance(item.get("selected_for_project"), bool) or not isinstance(item.get("implemented"), bool):
            raise ValueError("Los estados de selección e implementación deben ser booleanos")
        if item["scope"] not in ("selected", "excluded", "optional_operational"):
            raise ValueError("scope desconocido")
        if item["selected_for_project"] != (item["scope"] == "selected"):
            raise ValueError("scope y selected_for_project contradictorios")
        if item["implemented"] and not item["selected_for_project"]:
            raise ValueError("Una variable implementada debe estar seleccionada")
        if item.get("used_in_similarity") is not None:
            raise ValueError("El uso en similitud lo determina el comparador externo")


def build_document(metadata, sites, registry, registry_path=None, sites_path=None, processors=None):
    validate_sites(sites)
    validate_registry(registry)
    processors = processors or {}
    if {meta.variable for meta in metadata} != {"elevation", "roughness"} or len(metadata) != 2:
        raise ValueError("Se requiere un producto de elevación y uno de rugosidad")
    sources = {}
    for meta in metadata:
        sources[meta.variable] = {
            "product_id": meta.product_id,
            "pds_logical_identifier": meta.logical_identifier,
            "pds_label_version": meta.label_version,
            "scientific_product_version": meta.product_version,
            "url": SOURCE_BASE + meta.image_path.name.lower(),
            "observation_period": {"start": meta.observation_start, "stop": meta.observation_stop},
            "files": [_file_manifest(p) for p in (meta.xml_path, meta.label_path, meta.image_path)],
            "raster": {"rows": meta.rows, "columns": meta.columns, "dtype": "<f4", "byte_offset": 0},
            "transformation": {
                "formula": "raw * scaling_factor * 1000" if meta.variable == "elevation" else "raw * scaling_factor",
                "scaling_factor": meta.scale,
                "label_value_offset": meta.value_offset,
                "value_offset_added": False,
                "raw_unit": meta.raw_unit,
                "output_unit": "m",
                "vertical_reference": (
                    {"type": "sphere", "radius_m": meta.reference_radius_m}
                    if meta.variable == "elevation" else None
                ),
            },
            "warnings": list(meta.warnings),
        }
    sources["slope"] = {
        "kind": "derived_measurement",
        "derived_from": ["elevation"],
        "method": method_description(),
        "output_unit": "deg",
        "independent_nasa_product": False,
    }
    output_sites = []
    with ExitStack() as stack:
        readers = {meta.variable: stack.enter_context(LolaRaster(meta)) for meta in metadata}
        for site in sites:
            lat, lon = normalize_coordinates(site["latitude_deg"], site["longitude_deg"])
            measurements = {}
            for variable in registry["variables"]:
                key = variable["id"]
                if key in processors:
                    measurement = processors[key].sample(lat, lon)
                elif key == "slope":
                    measurement = readers["elevation"].sample_slope(lat, lon)
                    # Preservar exactamente la coordenada solicitada, antes de normalizar.
                    measurement["requested_coordinates"] = {
                        "latitude_deg": site["latitude_deg"], "longitude_deg": site["longitude_deg"]}
                elif key in readers:
                    measurement = readers[key].sample(lat, lon)
                else:
                    measurement = {
                        "value": None, "unit": variable["unit"], "available": False if variable["implemented"] else None,
                        "status": ("excluded" if variable["scope"] == "excluded" else
                                   "not_sampled" if variable["implemented"] else "not_implemented"),
                        "reason": (
                            "outside_current_analysis" if variable["scope"] == "excluded"
                            else "processor_not_configured" if variable["implemented"] else "processor_not_implemented"
                        ),
                        "source_ref": None,
                    }
                    bounds = variable.get("latitude_bounds_deg")
                    if bounds is not None:
                        inside = bounds[0] <= lat <= bounds[1]
                        measurement["within_declared_latitude_bounds"] = inside
                        if not inside:
                            measurement["available"] = False
                            measurement["reason"] = "outside_declared_latitude_coverage"
                measurement.update(
                    selected_for_project=variable["selected_for_project"],
                    implemented=variable["implemented"],
                    used_in_similarity=None,
                )
                measurements[key] = measurement
            output_sites.append({
                "id": site["id"], "name": site.get("name", site["id"]),
                "is_example": site["is_example"],
                "source": site.get("source"),
                "requested_coordinates": {
                    "latitude_deg": site["latitude_deg"], "longitude_deg": site["longitude_deg"],
                    "longitude_direction": "positive_east",
                },
                "normalized_coordinates": {"latitude_deg": lat, "longitude_deg_east": lon},
                "measurements": measurements,
            })
    for key, processor in processors.items():
        sources[key] = processor.manifest()
    configuration = {}
    if registry_path is not None:
        configuration["variable_registry"] = _file_manifest(Path(registry_path))
    if sites_path is not None:
        configuration["sites_input"] = _file_manifest(Path(sites_path))
    return {
        "schema_version": "1.0.0",
        "variable_registry_version": registry["registry_version"],
        "coordinate_reference": {
            "body": "Moon", "latitude_type": "planetocentric", "frame": FRAME,
            "longitude_direction": "positive_east", "normalized_longitude_interval": "[0, 360)",
        },
        "similarity": {"computed": False, "responsibility": "external_comparator"},
        "limitations": [
            "not_a_landing_safety_assessment", "native_pixel_not_local_point_measurement",
            "numeric_validity_does_not_establish_scientific_uncertainty",
            "lunar_elevation_and_roughness_not_automatically_equivalent_to_terrestrial_metrics",
            "slope_is_derived_at_ldem_grid_scale_not_a_point_or_landing_safety_measurement",
            "slope_east_west_spacing_shrinks_toward_poles_no_polar_accuracy_claim",
            "lunar_and_terrestrial_slope_boundary_missing_data_and_metric_policies_differ",
        ],
        "reproducibility": {
            "software": {
                "lunar_data": __version__, "python": platform.python_version(),
                "numpy": version("numpy"), "pvl": version("pvl"),
            },
            "code": [_file_manifest(p) for p in sorted(Path(__file__).parent.glob("*.py"))],
            "configuration": configuration,
            "policy": "deterministic_output_no_execution_timestamp",
        },
        "sources": sources,
        "sites": output_sites,
    }


def write_document(document, destination, protected_paths=()):
    """Serializa antes de escribir; no sobrescribe archivos existentes ni entradas."""
    destination = Path(destination).resolve()
    if destination in {Path(p).resolve() for p in protected_paths}:
        raise ValueError("La salida coincide con una entrada protegida")
    payload = json.dumps(document, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)
