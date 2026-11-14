"""CLI offline. Valores por defecto anclados al checkout, sin imports de FastAPI."""

import argparse
from pathlib import Path
import sys

from .export import build_document, read_json, validate_registry, validate_sites, write_document
from .metadata import MetadataError, load_metadata


def _repository_root():
    """Encuentra el checkout editable; fuera de él se usan rutas explícitas/cwd."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "backend/pyproject.toml").is_file() and (parent / "data/moon/variables.json").is_file():
            return parent
    return Path.cwd()


def main(argv=None):
    root = _repository_root()
    parser = argparse.ArgumentParser(description="Extraer elevación, rugosidad LOLA y pendiente derivada; no calcula similitud.")
    parser.add_argument("--data-root", type=Path, default=root / "NASA-Lunar-Studies/data/raw/lola")
    parser.add_argument("--registry", type=Path, default=root / "data/moon/variables.json")
    parser.add_argument("--output", required=True, type=Path)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--sites", type=Path, help="JSON con una lista de sitios")
    selection.add_argument("--latitude", type=float)
    parser.add_argument("--longitude", type=float, help="Grados, este positivo; acepta longitudes negativas")
    parser.add_argument("--site-id", default="coordinate_example")
    parser.add_argument("--example", action="store_true", help="Declara que las coordenadas son de prueba")
    args = parser.parse_args(argv)
    if args.sites is None and args.longitude is None:
        parser.error("--latitude requiere --longitude")
    if args.sites is not None and (args.longitude is not None or args.example or args.site_id != "coordinate_example"):
        parser.error("Con --sites, los ids e is_example se declaran en el archivo")
    try:
        if args.output.exists():
            raise ValueError("La salida ya existe; elegí otro nombre para conservar los resultados")
        registry = read_json(args.registry)
        validate_registry(registry)
        sites = read_json(args.sites) if args.sites else [{
            "id": args.site_id, "is_example": args.example,
            "latitude_deg": args.latitude, "longitude_deg": args.longitude,
        }]
        validate_sites(sites)
        metadata = [
            load_metadata(args.data_root / "ldem/ldem_16_float.xml"),
            load_metadata(args.data_root / "ldrm/ldrm_32_50_float.xml"),
        ]
        protected = [args.registry]
        if args.sites:
            protected.append(args.sites)
        for meta in metadata:
            protected.extend((meta.image_path, meta.xml_path, meta.label_path))
        document = build_document(metadata, sites, registry, args.registry, args.sites)
        write_document(document, args.output, protected)
    except (OSError, ValueError, KeyError, MetadataError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(f"JSON generado: {args.output.resolve()} ({len(sites)} sitio(s), LDEM + LDRM + pendiente derivada)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
