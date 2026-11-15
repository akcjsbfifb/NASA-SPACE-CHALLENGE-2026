"""Published lunar sites: the /moon adapter reads them by id."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.services.moon.moon_sites import MoonSites  # noqa: E402

SITES = REPO_ROOT / "data" / "moon" / "apollo_measurements.json"
TABLE = REPO_ROOT / "data" / "moon" / "apollo_measurements.csv"
FRONTEND = REPO_ROOT / "frontend" / "src" / "data" / "lunarLandings.ts"

EXPECTED = {"apollo-11", "apollo-12", "apollo-14", "apollo-15", "apollo-16", "apollo-17"}


@pytest.fixture(scope="module")
def document() -> dict:
    return json.loads(SITES.read_text())


def test_sites_are_the_frontend_landings():
    sites = MoonSites()
    assert set(sites.sites) == EXPECTED
    declared = FRONTEND.read_text()
    for site_id in EXPECTED:
        assert f"id: '{site_id}'" in declared


def test_sites_are_real_and_carry_provenance(document):
    for site in document["sites"]:
        assert site["is_example"] is False
        assert isinstance(site.get("source"), str) and site["source"].strip()
        assert -90 <= site["requested_coordinates"]["latitude_deg"] <= 90


def test_lola_values_are_available_and_measured(document):
    by_id = {site["id"]: site["measurements"] for site in document["sites"]}
    for site_id in EXPECTED:
        for key in ("elevation", "roughness", "slope"):
            item = by_id[site_id][key]
            assert item["available"] is True, (site_id, key)
            assert item["status"] == "valid"
    apollo11 = by_id["apollo-11"]
    assert apollo11["elevation"]["value"] == pytest.approx(-1915.036, abs=0.01)
    assert apollo11["elevation"]["unit"] == "m"
    assert apollo11["roughness"]["value"] == pytest.approx(0.3518, abs=0.0002)
    assert apollo11["slope"]["value"] == pytest.approx(0.8693, abs=0.0002)


def test_diviner_and_hydrogen_are_available_for_apollo(document):
    by_id = {site["id"]: site["measurements"] for site in document["sites"]}
    for key in (
        "rock_abundance",
        "bolometric_temperature",
        "regolith_temperature",
        "hydrogen_abundance_ppm",
    ):
        item = by_id["apollo-11"][key]
        assert item["available"] is True
        assert item["status"] == "valid"


def test_find_builds_the_endpoint_payload():
    payload = MoonSites().find("apollo-11")
    assert payload is not None
    assert payload["site"] == "apollo-11"
    assert payload["elevation_m"] == pytest.approx(-1915.036, abs=0.01)
    assert payload["roughness_m"] == pytest.approx(0.3518, abs=0.0002)
    assert payload["slope_deg"] == pytest.approx(0.8693, abs=0.0002)
    assert payload["compared"] == []
    assert "hydrogen_abundance_ppm" not in payload["unavailable"]
    assert payload["elevation_status"] == "valid"


def test_unknown_site_and_missing_file(tmp_path):
    assert MoonSites().find("apollo-13") is None
    broken = MoonSites(tmp_path / "missing.json")
    assert broken.error and broken.sites == {}


def test_csv_matches_the_json(document):
    with TABLE.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["site_id"] for row in rows] == [site["id"] for site in document["sites"]]
    assert len(rows[0]) == 33
    assert rows[0]["elevation_m"] == str(
        document["sites"][0]["measurements"]["elevation"]["value"]
    )
