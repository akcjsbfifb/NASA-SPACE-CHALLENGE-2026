"""Vista CSV ancha del JSON científico; sólo biblioteca estándar, sin lectores NASA.

Ejecutar: python -m lunar_data.csv_export --input mediciones.json --output mediciones.csv
El JSON original es la autoridad científica y nunca se modifica.
"""

import argparse
import csv
import hashlib
import io
import json
import math
from pathlib import Path


# Orden estable. Nuevas variables requieren una entrada y unidad verificadas;
# no se agregan columnas ni se inventan valores por inspeccionar otros productos.
VARIABLE_COLUMNS = (
    ("elevation", "elevation_m", "m"),
    ("roughness", "roughness_m", "m"),
    ("slope", "slope_deg", "deg"),
)
FULL_VARIABLE_COLUMNS = VARIABLE_COLUMNS + (
    ("rock_abundance", "rock_abundance_fraction", "1"),
    ("bolometric_temperature", "bolometric_temperature_K", "K"),
    ("regolith_temperature", "regolith_temperature_K", "K"),
)


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} debe ser un número finito")
    return value


def _boolean_cell(value):
    return "" if value is None else "true" if value else "false"


def render_csv(document, *, source_json_file, source_json_sha256, profile="core"):
    """Serializa sin redondear, normalizar coordenadas ni recalcular mediciones."""
    if profile == "lend":
        return render_lend_csv(document, source_json_file=source_json_file, source_json_sha256=source_json_sha256)
    if not isinstance(document, dict) or document.get("schema_version") != "1.0.0":
        raise ValueError("Contrato JSON científico incompatible")
    reference = document.get("coordinate_reference", {})
    if not isinstance(reference, dict) or (reference.get("body"), reference.get("latitude_type"), reference.get("longitude_direction")) != (
        "Moon", "planetocentric", "positive_east"
    ):
        raise ValueError("Se requieren coordenadas lunares planetocéntricas, este positivo")
    sites = document.get("sites")
    if not isinstance(sites, list) or not sites:
        raise ValueError("Se requiere una lista no vacía de sitios")
    if profile not in ("core", "full"):
        raise ValueError("Perfil CSV desconocido")
    columns = VARIABLE_COLUMNS if profile == "core" else FULL_VARIABLE_COLUMNS
    fields = ["site_id", "latitude_deg", "longitude_deg"]
    fields += [column for _, column, _ in columns]
    for variable, _, _ in columns:
        fields += [f"{variable}_status", f"{variable}_available", f"{variable}_reason"]
    fields += ["source_json_file", "source_json_sha256"]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    seen = set()
    for site in sites:
        if not isinstance(site, dict):
            raise ValueError("Cada sitio debe ser un objeto")
        site_id = site.get("id")
        if not isinstance(site_id, str) or not site_id.strip() or site_id in seen:
            raise ValueError("Cada sitio requiere un id no vacío y único")
        seen.add(site_id)
        coordinates = site.get("requested_coordinates", {})
        if not isinstance(coordinates, dict):
            raise ValueError("Faltan coordenadas solicitadas")
        latitude = _number(coordinates.get("latitude_deg"), "latitude_deg")
        longitude = _number(coordinates.get("longitude_deg"), "longitude_deg")
        if not -90 <= latitude <= 90:
            raise ValueError("Latitud fuera de [-90, 90]")
        row = {"site_id": site_id, "latitude_deg": latitude, "longitude_deg": longitude,
               "source_json_file": source_json_file, "source_json_sha256": source_json_sha256}
        measurements = site.get("measurements", {})
        if not isinstance(measurements, dict):
            raise ValueError("Faltan mediciones científicas")
        for variable, column, unit in columns:
            measurement = measurements.get(variable)
            if not isinstance(measurement, dict):
                raise ValueError(f"Falta el registro científico de {variable} en {site_id}")
            status = measurement.get("status")
            reason = measurement.get("reason")
            available = measurement.get("available")
            if not isinstance(status, str) or not status:
                raise ValueError(f"Falta status de {variable}")
            if reason is not None and not isinstance(reason, str):
                raise ValueError(f"reason inválido en {variable}")
            if "available" not in measurement or (available is not None and not isinstance(available, bool)):
                raise ValueError(f"available inválido en {variable}")
            if measurement.get("unit") != unit:
                raise ValueError(f"Unidad incompatible en {variable}; se requiere {unit}")
            if "value" not in measurement:
                raise ValueError(f"Falta value de {variable}")
            value = measurement["value"]
            if available is True:
                if status != "valid":
                    raise ValueError(f"Estado y disponibilidad contradictorios en {variable}")
                row[column] = _number(value, variable)
            else:
                if value is not None or status == "valid":
                    raise ValueError(f"Valor y disponibilidad contradictorios en {variable}")
                row[column] = ""
            row[f"{variable}_status"] = status
            row[f"{variable}_available"] = _boolean_cell(available)
            row[f"{variable}_reason"] = reason if reason is not None else ""
        writer.writerow(row)
    return buffer.getvalue()


def render_lend_csv(document, *, source_json_file, source_json_sha256):
    """Tabla auxiliar: fila por sitio/producto/canal; jamás mezcla períodos."""
    fields = ["site_id", "latitude_deg", "longitude_deg", "product_id", "period_start", "period_stop",
              "channel", "quantity", "value", "unit", "unit_status", "statistical_error", "exposure_s",
              "raw_value", "raw_statistical_error", "raw_exposure_s", "status", "available", "reason",
              "source_ref", "record_index", "source_json_file", "source_json_sha256"]
    if not isinstance(document, dict) or document.get("schema_version") != "1.0.0":
        raise ValueError("Contrato JSON incompatible")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    seen = set()
    for site in document["sites"]:
        for item in site["measurements"].get("lend_neutron_indicator", {}).get("observations", []):
            identity = (site["id"], item["product_id"], item["channel"])
            if identity in seen:
                raise ValueError("Observación LEND duplicada")
            seen.add(identity)
            row = {key: item.get(key) for key in fields if key in item}
            row.update(site_id=site["id"], **{k: site["requested_coordinates"][k] for k in ["latitude_deg", "longitude_deg"]},
                       period_start=item["period"]["start"], period_stop=item["period"]["stop"],
                       available=_boolean_cell(item["available"]),
                       record_index=(item.get("sampling") or {}).get("record_index"),
                       source_json_file=source_json_file, source_json_sha256=source_json_sha256)
            for key in ["value", "statistical_error", "exposure_s", "raw_value", "raw_statistical_error", "raw_exposure_s"]:
                if row.get(key) is not None:
                    _number(row[key], key)
            if not isinstance(item["available"], bool):
                raise ValueError("Disponibilidad LEND debe ser booleana")
            if item["available"]:
                if item["value"] is None or item["status"] != "valid":
                    raise ValueError("Observable LEND disponible sin valor o estado válido")
            elif item["value"] is not None:
                raise ValueError("Observable LEND no disponible con valor contradictorio")
            writer.writerow(row)
    return buffer.getvalue()


def export_csv(source, destination, profile="core"):
    """Lee exclusivamente el JSON, valida todo y crea una salida nueva UTF-8/LF."""
    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError("La salida no puede ser el JSON de entrada")
    if source.suffix.lower() != ".json" or destination.suffix.lower() != ".csv":
        raise ValueError("Se requiere entrada .json y salida .csv")
    if destination.exists():
        raise FileExistsError("La salida ya existe; elegí otro nombre para conservarla")
    raw = source.read_bytes()
    def invalid_constant(value):
        raise ValueError(f"Constante JSON no permitida: {value}")
    document = json.loads(raw.decode("utf-8-sig"), parse_constant=invalid_constant)
    payload = render_csv(document, source_json_file=source.name,
                         source_json_sha256=hashlib.sha256(raw).hexdigest(), profile=profile)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="") as stream:
        stream.write(payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Convertir JSON científico lunar a CSV ancho, sin abrir datos NASA.")
    parser.add_argument("--input", required=True, type=Path, help="JSON científico completo, que se conserva")
    parser.add_argument("--output", required=True, type=Path, help="CSV nuevo; nunca se sobrescribe")
    parser.add_argument("--profile", choices=("core", "full", "lend"), default="core", help="core: 17 columnas; full: fuentes raster; lend: tabla auxiliar por producto/canal")
    args = parser.parse_args(argv)
    try:
        export_csv(args.input, args.output, args.profile)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(f"CSV generado: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
