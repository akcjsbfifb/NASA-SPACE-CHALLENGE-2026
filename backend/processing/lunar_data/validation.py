"""Validaciones ejecutadas y pendientes; ninguna comprobación interna es externa."""

import argparse
import json
import math
from pathlib import Path
import struct


def validate_lend(root, config, sites):
    from .lend import LendProduct
    results=[]
    for source in config.get("lend",[]):
        with LendProduct(root/source["xml"]) as product, product.data_path.open("rb") as independent:
            checks=[]
            for site in sites:
                for channel in source["channels"]:
                    lat,lon=site["latitude_deg"],site["longitude_deg"]
                    measured=product.sample(lat,lon,channel)
                    check={"site_id":site["id"],"channel":channel,"measurement":measured}
                    if abs(lat)>=80:
                        check["independent_status"]="OUTSIDE_COVERAGE"
                    else:
                        row=int(math.floor(80-lat));column=int(math.floor(lon%360))
                        independent.seek((row*360+column)*310)
                        record=independent.read(310)
                        offset={"SETN":70,"CSETN":106,"STN1":58,"STN2":82,"STN3":94}[channel]
                        exposure,rate,error=struct.unpack_from(">fff",record,offset)
                        assert (measured["raw_exposure_s"],measured["raw_value"],measured["raw_statistical_error"]) == (exposure,rate,error)
                        assert struct.unpack_from(">ff",record,46)==(79.5-row,column+.5)
                        check.update(independent_status="PASS",independent_raw_exposure_s=exposure,
                                     independent_raw_rate=rate,independent_raw_error=error,
                                     independent_method="separate seek/struct big-endian decoder and grid calculation")
                    checks.append(check)
            results.append({"source":product.manifest(),"checks":checks})
    return {"products":results,"external_validation":"PENDING; binary decoder checks are internal numeric validation",
            "unit_policy":"RATE/ERR units not declared; exposure seconds per PDS4; no hydrogen conversion"}


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
    parser.add_argument("--lend", action="store_true", help="Comprobación local independiente ALDE")
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--sites", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("La salida debe ser nueva")
    root = Path(__file__).resolve().parents[3]
    if not args.remote_diviner and not args.lend:
        parser.error("Elegir una comprobación explícita; --remote-diviner autoriza HTTP acotado")
    config=json.loads(args.sources.read_text(encoding="utf-8"))
    sites=json.loads(args.sites.read_text(encoding="utf-8"))
    if args.remote_diviner:
        result=validate_diviner(root,config,sites)
    else:
        result=validate_lend(root,config,sites)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    print(f"Validación ejecutada: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
