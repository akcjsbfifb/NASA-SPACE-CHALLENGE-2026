"""Search Earth for places close to a lunar target.

  .venv/bin/python backend/scripts/search_earth.py --precision 0.85 \
      --target slope=8 --target roughness=30 --target temperature=-20 \
      --target ice=0 --target rock=vb

Any variable declared in data/earth/analogs.json can be passed with --target,
so a new column needs no change here.

Precision near 1 returns a few very close places.
Precision near 0 returns more places that match less tightly.
The shortlist is written to data/earth/shortlist.json for a later AI filter.
"""

from __future__ import annotations

import argparse
import time

from similarity import EarthIndex, parse_criteria, write_shortlist


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        metavar="ID=VALUE",
        help="variable declared in data/earth/analogs.json; repeatable",
    )
    parser.add_argument("--precision", type=float, default=0.7)
    parser.add_argument("--min-worst", type=float, default=None)
    args = parser.parse_args()

    values: dict[str, str] = {}
    for item in args.target:
        if "=" not in item:
            parser.error(f"--target espera id=valor, llegó {item!r}")
        name, raw = item.split("=", 1)
        values[name.strip()] = raw.strip()

    started = time.perf_counter()
    index = EarthIndex()
    loaded = time.perf_counter()
    result = index.search(
        parse_criteria(index.contract, values),
        precision=args.precision,
        min_worst=args.min_worst,
    )
    path = write_shortlist(result)
    finished = time.perf_counter()

    print(f"celdas: {index.lat.size:,}")
    print(f"cargar: {loaded - started:.2f} s")
    print(f"buscar: {finished - loaded:.2f} s")
    print(
        f"precision={result['precision']} cercania_minima={result['min_closeness']} "
        f"devueltos={result['returned']} de tope {result['limit']}"
    )
    print(f"variables: {', '.join(result['variables'])}")
    print(f"temperatura: {result['temperature_mode']}")
    print(f"shortlist: {path}")
    for point in result["points"][:8]:
        print(
            f"{point['lat']:8.3f}, {point['lon']:8.3f}  "
            f"cercania={point['closeness']:.2f}  cobertura={point['coverage']}  "
            f"slope={point['slope_deg']} rough={point['roughness_m']} "
            f"tmin={point['tmin_c']} ice={point['ice_thickness_m']} rock={point['rock']}"
        )


if __name__ == "__main__":
    main()
