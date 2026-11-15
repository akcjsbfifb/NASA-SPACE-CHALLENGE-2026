from __future__ import annotations

import os
from pathlib import Path

from app.services.earth.similarity import EarthIndex
from app.services.moon.lola_sampler import MoonSampler
from app.services.moon.moon_sites import MoonSites

_index: EarthIndex | None = None
_moon: MoonSampler | None = None
_moon_sites: MoonSites | None = None


def earth_index() -> EarthIndex:
    global _index
    if _index is None:
        external = os.environ.get("GURVICH_COLUMNS_DIR", "").strip()
        _index = EarthIndex(columns_dir=Path(external) if external else None)
    return _index


def reset_earth_index(index: EarthIndex | None) -> None:
    global _index
    _index = index


def moon_sites() -> MoonSites:
    global _moon_sites
    if _moon_sites is None:
        _moon_sites = MoonSites()
    return _moon_sites


def moon_sampler() -> MoonSampler:
    global _moon
    if _moon is None:
        _moon = MoonSampler()
    return _moon
