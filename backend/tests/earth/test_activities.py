"""The activity catalog and resolve(): targets, assigned weights, error codes."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.services.earth.activities import ActivityError, load_catalog, resolve  # noqa: E402

VARIABLES = ("slope", "roughness", "temperature", "ice", "rock")
CONTINUOUS = ("slope", "roughness", "temperature", "ice")
LANGUAGES = ("es", "en", "fr", "it")

CATALOG_IDS = [
    "rover_wheels",
    "landing_site",
    "polar_ice",
    "sample_basalt",
    "floor_sample",
    "viper_ice_prospect",
    "artemis_polar_landing",
    "sample_pyroclastic",
    "spa_norite",
    "hadley_rille",
    "surveyor_regolith",
    "light_mantle",
]


def _written_catalog(tmp_path: Path, catalog: list[dict]) -> Path:
    path = tmp_path / "activities.json"
    path.write_text(json.dumps(catalog))
    return path


def test_catalog_has_the_twelve_presets_in_order():
    catalog = load_catalog()
    assert [preset["id"] for preset in catalog] == CATALOG_IDS
    for preset in catalog:
        assert set(preset["weights"]) == set(VARIABLES)
        assert set(preset["search"]) == set(VARIABLES)
        assert set(preset["measured"]) <= set(VARIABLES)
        assert set(preset["serves"]) == set(LANGUAGES)


def test_every_preset_searches_a_continuous_variable():
    for preset in load_catalog():
        searched = [
            name
            for name in CONTINUOUS
            if preset["weights"][name] > 0 and preset["search"][name] is not None
        ]
        assert searched, preset["id"]


def test_floor_sample_rock_is_the_only_weight_without_a_target():
    missing = {
        (preset["id"], name)
        for preset in load_catalog()
        for name in VARIABLES
        if preset["weights"][name] > 0 and preset["search"][name] is None
    }
    assert missing == {("floor_sample", "rock")}


def test_load_catalog_rejects_a_preset_without_a_continuous_search(tmp_path):
    catalog = json.loads((REPO_ROOT / "mcp" / "activities.json").read_text())
    preset = next(item for item in catalog if item["id"] == "landing_site")
    preset["search"] = {name: None for name in VARIABLES}
    with pytest.raises(ValueError, match="landing_site"):
        load_catalog(_written_catalog(tmp_path, catalog))


def test_load_catalog_rejects_a_weight_without_a_target(tmp_path):
    catalog = json.loads((REPO_ROOT / "mcp" / "activities.json").read_text())
    preset = next(item for item in catalog if item["id"] == "sample_basalt")
    preset["search"]["rock"] = None
    with pytest.raises(ValueError, match="sample_basalt"):
        load_catalog(_written_catalog(tmp_path, catalog))


def test_resolve_without_activity_or_weights_passes_targets_through():
    targets, weights, activity = resolve(None, {}, {})
    assert targets == {}
    assert weights == {name: None for name in VARIABLES}
    assert activity is None


def test_polar_ice_merges_its_search_values():
    targets, weights, activity = resolve("polar_ice", {}, {})
    assert targets == {"temperature": -140, "ice": 1}
    assert weights == {
        "slope": None,
        "roughness": None,
        "temperature": 1,
        "ice": 1,
        "rock": None,
    }
    assert activity is not None and activity["id"] == "polar_ice"


def test_floor_sample_drops_rock_when_the_request_has_no_code():
    targets, weights, _activity = resolve("floor_sample", {}, {})
    assert targets == {"slope": 3, "roughness": 5}
    assert "rock" not in targets
    assert weights == {
        "slope": 0.3,
        "roughness": 1,
        "temperature": None,
        "ice": None,
        "rock": None,
    }


def test_floor_sample_scores_rock_when_the_request_names_it():
    targets, weights, _activity = resolve("floor_sample", {"rock": "vb"}, {})
    assert targets["rock"] == "vb"
    assert targets["slope"] == 3
    assert weights["rock"] == 1


def test_viper_ice_prospect_merges_four_search_values():
    targets, _weights, _activity = resolve("viper_ice_prospect", {}, {})
    assert targets == {"slope": 15, "roughness": 20, "temperature": -140, "ice": 1}


def test_request_target_beats_the_preset_value():
    targets, weights, _activity = resolve("hadley_rille", {"slope": 5}, {})
    assert targets["slope"] == 5
    assert weights["slope"] == 1


def test_request_weight_zero_is_returned_as_zero():
    _targets, weights, _activity = resolve("polar_ice", {}, {"temperature": 0})
    assert weights["temperature"] == 0
    assert weights["ice"] == 1


@pytest.mark.parametrize(
    "weights",
    [
        {"temperature": "x"},
        {"banana": 1},
        {"ice": 1.5},
        {"ice": math.nan},
        {"ice": math.inf},
        {"ice": True},
        {"ice": -0.1},
    ],
)
def test_bad_weights_are_rejected(weights: dict):
    with pytest.raises(ActivityError) as error:
        resolve("polar_ice", {}, weights)
    assert error.value.code == "bad_weight"


def test_unknown_activity_is_rejected():
    with pytest.raises(ActivityError) as error:
        resolve("no_such", {}, {})
    assert error.value.code == "unknown_activity"


def test_partial_request_weights_leave_the_rest_at_one():
    targets, weights, activity = resolve(None, {"slope": 5, "roughness": 10}, {"slope": 0})
    assert targets == {"slope": 5, "roughness": 10}
    assert weights["slope"] == 0
    assert weights["roughness"] == 1
    assert weights["temperature"] is None
    assert activity is None


def test_zeroed_weights_with_no_remaining_target_is_no_measurement():
    with pytest.raises(ActivityError) as error:
        resolve("landing_site", {}, {"slope": 0, "roughness": 0})
    assert error.value.code == "no_measurement"
    assert error.value.message == "falta al menos una medición"
