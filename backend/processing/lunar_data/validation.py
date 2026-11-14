"""Validaciones ejecutadas y pendientes; ninguna comprobación interna es externa."""

import argparse
import json
import math
from pathlib import Path
import struct


def validate_diviner(root, config, sites):
    import rasterio
    import tifffile
    from .diviner import DivinerRaster
    from .http_range import TransferBudget
    budget = TransferBudget(config.get("http_budget_bytes", 16 * 1024 * 1024))
    results = []
    for variable, source in config.get("diviner", {}).items():
        with DivinerRaster(variable, root / source["xml"], source.get("raster"), budget) as raster:
            samples = []
            for site in sites:
                lat, lon = site["latitude_deg"], site["longitude_deg"]
                primary = raster.sample(lat, lon)
                check = {"site_id": site["id"], "measurement": primary}
                if primary["sampling"] is None:
                    check["independent_status"] = "OUTSIDE_COVERAGE"
                else:
                    row = min(math.floor((70 - lat) * 128), 17919)
                    col = math.floor((((lon + 180) % 360) / (1/128)))
                    handle = raster.remote.open() if raster.remote else Path(raster.location).open("rb")
                    with handle as stream, tifffile.TiffFile(stream) as tf:
                        page = tf.pages[0]
                        if page.is_tiled or int(page.compression) != 1 or page.rowsperstrip != 1:
                            raise ValueError("Lectura independiente Diviner requiere TIFF sin compresión, una fila por strip")
                        offset = page.dataoffsets[row] + 4 * col
                        stream.seek(offset)
                        independent = struct.unpack("<f", stream.read(4))[0]
                    if math.isfinite(independent):
                        assert primary["raw_value"] == independent
                    else:
                        assert primary["status"] == "missing"
                        independent = None
                    assert (primary["sampling"]["row"], primary["sampling"]["column"]) == (row, col)
                    check.update(independent_raw_value=independent, independent_status="PASS",
                                 independent_method="tifffile strip offset + seek/struct float32; separate coordinate calculation")
                samples.append(check)
            results.append({"variable": variable, "source": raster.manifest(), "samples": samples})
    return {"products": results, "http_body_bytes_received": budget.received,
            "http_body_limit_bytes": budget.limit,
            "transfer_scope": "consumed response bodies, excluding HTTP headers and TLS",
            "software": {"rasterio": rasterio.__version__, "gdal": rasterio.__gdal_version__, "tifffile": tifffile.__version__},
            "external_validation": "PENDING; independent byte decoder is not external geodetic validation"}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Verificaciones lunares reales; red sólo con --remote-diviner")
    parser.add_argument("--remote-diviner", action="store_true")
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--sites", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("La salida debe ser nueva")
    root = Path(__file__).resolve().parents[3]
    if not args.remote_diviner:
        parser.error("Elegir una comprobación explícita; --remote-diviner autoriza HTTP acotado")
    result = validate_diviner(root, json.loads(args.sources.read_text(encoding="utf-8")),
                              json.loads(args.sites.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    print(f"Diviner verificado: {result['http_body_bytes_received']} bytes HTTP; {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
