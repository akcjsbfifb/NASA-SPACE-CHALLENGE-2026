"""Regeneración local con evidencia Diviner previa: nunca hace consultas HTTP."""

from contextlib import ExitStack
from copy import deepcopy
import hashlib
import json

import pytest

from lunar_data.export import build_document, read_json, _file_manifest, write_document
from lunar_data.lend import LendProduct, LendCollection
from lunar_data.metadata import load_metadata
from lunar_data.csv_export import render_csv


def rebuild_from_local_references(repo_root):
    """Fixture de reproducibilidad, no nuevo procesador ni validación Diviner externa."""
    root = repo_root
    registry = root / "data/moon/variables.json"
    sites_path = root / "backend/tests/lunar/fixtures/sites.example.json"
    config_path = root / "data/moon/sources.example.json"
    sites, config = read_json(sites_path), read_json(config_path)
    evidence = read_json(root / "data/moon/validation.diviner.json")
    coordinates = {s["id"]: (s["latitude_deg"], s["longitude_deg"] % 360) for s in sites}

    class VerifiedReference:
        def __init__(self, entry):
            self.entry = entry
            self.values = {coordinates[s["site_id"]]: s["measurement"] for s in entry["samples"]}

        def sample(self, lat, lon):
            return deepcopy(self.values[(lat, lon % 360)])

        def manifest(self):
            return deepcopy(self.entry["source"])

    processors = {}
    for entry in evidence["products"]:
        xml = root / config["diviner"][entry["variable"]]["xml"]
        assert hashlib.sha256(xml.read_bytes()).hexdigest() == entry["source"]["files"][0]["sha256"]
        processors[entry["variable"]] = VerifiedReference(entry)
    raw = root / "NASA-Lunar-Studies/data/raw/lola"
    metadata = [load_metadata(raw / folder / (name + ".xml")) for folder, name in
                [("ldem", "ldem_16_float"), ("ldrm", "ldrm_32_50_float")]]
    with ExitStack() as stack:
        selections = [(stack.enter_context(LendProduct(root / item["xml"])), item["channels"])
                      for item in config["lend"]]
        processors["lend_neutron_indicator"] = LendCollection(selections)
        result = build_document(metadata, sites, read_json(registry), registry, sites_path, processors)
    result["reproducibility"]["configuration"]["additional_sources"] = _file_manifest(config_path)
    result["reproducibility"]["configuration"]["reused_diviner_evidence"] = _file_manifest(
        root / "data/moon/validation.diviner.json")
    return result


@pytest.mark.local_data
def test_complete_json_reproducible_from_local_verified_references(repo_root, tmp_path, monkeypatch):
    if not (repo_root / "NASA-Lunar-Studies/data/raw/lola/ldem/ldem_16_float.img").exists():
        pytest.skip("Originales locales no incluidos en Git")
    monkeypatch.setattr("lunar_data.http_range.urlopen", lambda *a, **k: pytest.fail("HTTP prohibido en regeneración local"))
    first = rebuild_from_local_references(repo_root)
    second = rebuild_from_local_references(repo_root)
    assert first == second
    original = read_json(repo_root / "data/moon/lola_measurements.example.json")
    for key in ["sites", "sources", "coordinate_reference", "variable_registry_version", "limitations"]:
        assert first[key] == original[key]
    write_document(first, tmp_path / "first.json")
    write_document(second, tmp_path / "second.json")
    assert (tmp_path / "first.json").read_bytes() == (tmp_path / "second.json").read_bytes()
    if first["reproducibility"] == original["reproducibility"]:
        assert (tmp_path / "first.json").read_bytes() == (repo_root / "data/moon/lola_measurements.example.json").read_bytes()


@pytest.mark.parametrize("profile,filename,columns", [
    ("core", "lola_measurements.example.csv", 17),
    ("full", "lunar_measurements.example.csv", 29),
    ("lend", "lend_observations.example.csv", 23),
])
def test_all_csv_profiles_reproduce_published_bytes(repo_root, profile, filename, columns):
    import csv
    import io
    source = repo_root / "data/moon/lola_measurements.example.json"
    raw = source.read_bytes()
    text = render_csv(json.loads(raw), source_json_file=source.name,
                      source_json_sha256=hashlib.sha256(raw).hexdigest(), profile=profile)
    assert text.encode("utf-8") == (repo_root / "data/moon" / filename).read_bytes()
    reader = csv.DictReader(io.StringIO(text))
    assert len(reader.fieldnames) == columns
    assert len(list(reader)) == (8 if profile == "lend" else 2)


def test_polar_illumination_is_optional_and_never_darkness_by_default(repo_root):
    registry = read_json(repo_root / "data/moon/variables.json")
    item = next(v for v in registry["variables"] if v["id"] == "polar_solar_illumination")
    assert item["scope"] == "optional_operational"
    assert item["implemented"] is False and item["selected_for_project"] is False
    document = read_json(repo_root / "data/moon/lola_measurements.example.json")
    for site in document["sites"]:
        value = site["measurements"]["polar_solar_illumination"]
        assert value["value"] is None and value["implemented"] is False
        assert value["selected_for_project"] is False and value["used_in_similarity"] is None
