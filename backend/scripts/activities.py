"""Activity presets: one catalog, one merge, one place for weights.

`mcp/activities.json` holds the presets. The MCP forwards the activity id and
the weights the model chose; this module turns both into the criteria and the
weights that `EarthIndex.search` consumes. No preset number is decided here.

A variable enters the search only if it has a target and a weight above zero.
That filter lives in `EarthIndex.search`. `resolve` returns every target of the
merge, weight 0 included, so the caller can report what it asked for.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "mcp" / "activities.json"

VARIABLES = ("slope", "roughness", "temperature", "ice", "rock")
CONTINUOUS = ("slope", "roughness", "temperature", "ice")

# `floor_sample` leaves rock null on purpose: the floor type is scored only when
# the request carries a rock code. Every other positive weight has a search
# value, which is what load_catalog enforces.
NULL_TARGET_ALLOWED = frozenset({("floor_sample", "rock")})


class ActivityError(Exception):
    """A request the catalog cannot serve, with the code the HTTP layer emits."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def load_catalog(path: Path | None = None) -> list[dict]:
    """Read the activity catalog and enforce the two invariants it must hold.

    A preset that searches only variables with a null target saturates closeness
    at 1.0 and returns places at random, so it is rejected here instead of
    producing a confident list of nothing.
    """
    source = CATALOG if path is None else Path(path)
    catalog = json.loads(source.read_text())
    if not isinstance(catalog, list) or not catalog:
        raise ValueError(f"{source.name}: falta la lista de actividades")
    seen: set[str] = set()
    for preset in catalog:
        name = preset.get("id")
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError(f"{source.name}: id vacío o duplicado")
        seen.add(name)
        weights = preset.get("weights") or {}
        search = preset.get("search") or {}
        searched = [
            key
            for key in CONTINUOUS
            if float(weights.get(key) or 0.0) > 0.0 and search.get(key) is not None
        ]
        if not searched:
            raise ValueError(f"{source.name}: {name} no busca ninguna variable continua")
        for key in VARIABLES:
            if float(weights.get(key) or 0.0) <= 0.0:
                continue
            if search.get(key) is None and (name, key) not in NULL_TARGET_ALLOWED:
                raise ValueError(f"{source.name}: {name} tiene peso en {key} y no tiene target")
    return catalog


def resolve(
    activity_id: str | None,
    targets: dict[str, float | str],
    weights: dict[str, float],
) -> tuple[dict[str, float | str], dict[str, float | None], dict | None]:
    """Merge the request and the preset into targets, weights and the activity.

    The first dict is the merge: a key is there if the request carries it or the
    preset has a search value. The second dict always has the five keys, with the
    assigned weight (0 included) when the key has a target and None when it does
    not. The third is the preset object, or None when no activity was asked for.
    """
    activity_id = activity_id or None  # an empty choice means no activity
    weights = weights or {}
    requested = _validated_weights(weights)
    preset = None if activity_id is None else _find(load_catalog(), activity_id)

    merged: dict[str, float | str] = {
        name: value
        for name, value in targets.items()
        if value is not None and value != ""
    }
    if preset is not None:
        for name in VARIABLES:
            value = preset["search"].get(name)
            if name not in merged and value is not None:
                merged[name] = value

    assigned: dict[str, float | None] = {}
    for name in VARIABLES:
        if name not in merged:
            assigned[name] = None
        elif name in requested:
            assigned[name] = requested[name]
        elif preset is None:
            assigned[name] = 1.0
        else:
            assigned[name] = float(preset["weights"].get(name, 1.0))

    # Without an activity or explicit weights this is a pass-through. An empty
    # search is only an error when the request itself narrowed it, and the
    # caller gets the code the HTTP layer reports.
    if activity_id is not None or requested:
        if not any(value is not None and value > 0.0 for value in assigned.values()):
            raise ActivityError("no_measurement", "falta al menos una medición")
    return merged, assigned, preset


def _validated_weights(weights: dict) -> dict[str, float]:
    """Request weights as floats, or bad_weight naming the first key at fault."""
    checked: dict[str, float] = {}
    for name, value in weights.items():
        if name not in VARIABLES:
            raise ActivityError("bad_weight", f"peso desconocido: {name}")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ActivityError("bad_weight", f"peso no numérico en {name}")
        number = float(value)
        if not math.isfinite(number):
            raise ActivityError("bad_weight", f"peso no finito en {name}")
        if number < 0.0 or number > 1.0:
            raise ActivityError("bad_weight", f"peso fuera de [0, 1] en {name}")
        checked[name] = number
    return checked


def _find(catalog: list[dict], activity_id: str) -> dict:
    for preset in catalog:
        if preset.get("id") == activity_id:
            return preset
    raise ActivityError("unknown_activity", f"actividad desconocida: {activity_id}")
