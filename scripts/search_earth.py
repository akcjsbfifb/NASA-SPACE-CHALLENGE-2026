"""Search Earth for places close to a five-parameter lunar target.

  .venv/bin/python scripts/search_earth.py --precision 0.85 --slope 8 --roughness 30 --tmin -20 --ice 0 --rock vb

Precision near 1 returns a few very close places.
Precision near 0 returns more places that match less tightly.
The shortlist is written to data/earth/shortlist.json for a later AI filter.
"""

from __future__ import annotations

import argparse
import time

from similarity import EarthIndex, write_shortlist


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slope", type=float, required=True)
    parser.add_argument("--roughness", type=float, required=True)
    parser.add_argument("--tmin", type=float, required=True)
    parser.add_argument("--ice", type=float, required=True)
    parser.add_argument("--rock", required=True)
    parser.add_argument("--precision", type=float, default=0.7)
    args = parser.parse_args()

    started = time.perf_counter()
    index = EarthIndex()
    loaded = time.perf_counter()
    result = index.search(
        slope=args.slope,
        roughness=args.roughness,
        tmin=args.tmin,
        ice=args.ice,
        rock=args.rock,
        precision=args.precision,
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
    print(f"temperatura: {result['temperature_mode']}")
    print(f"shortlist: {path}")
    for point in result["points"][:8]:
        print(
            f"{point['lat']:8.3f}, {point['lon']:8.3f}  "
            f"cercania={point['closeness']:.2f}  "
            f"slope={point['slope_deg']} rough={point['roughness_m']} "
            f"tmin={point['tmin_c']} ice={point['ice_thickness_m']} rock={point['rock']}"
        )


if __name__ == "__main__":
    main()
