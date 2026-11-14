from copy import deepcopy
import json

import pytest

from lunar_data.export import build_document, read_json, validate_registry, validate_sites, write_document


def test_extensible_document_deterministic_no_invented_values(metadata_pair, registry_path, tmp_path):
    registry = read_json(registry_path)
    sites = [{"id": "test", "is_example": True, "latitude_deg": -85, "longitude_deg": -10}]
    first = build_document(metadata_pair, sites, registry, registry_path)
    second = build_document(metadata_pair, sites, registry, registry_path)
    assert first == second
    assert first["similarity"]["computed"] is False
    measures = first["sites"][0]["measurements"]
    assert measures["elevation"]["available"] is True
    assert measures["elevation"]["quality"]["uncertainty_m"] is None
    assert measures["rock_abundance"]["implemented"] is False
    assert measures["rock_abundance"]["selected_for_project"] is True
    assert measures["rock_abundance"]["available"] is False  # fuera de ±70°
    assert measures["rock_abundance"]["status"] == "not_implemented"
    assert measures["rock_abundance"]["value"] is None
    assert measures["slope"]["status"] == "not_implemented"
    assert measures["slope"]["selected_for_project"] is True
    assert measures["slope"]["implemented"] is False
    slope_definition = next(item for item in registry["variables"] if item["id"] == "slope")
    assert slope_definition["implementation_status"] == "in_development_external"
    assert measures["lend_neutron_indicator"]["status"] == "not_implemented"
    assert measures["lend_neutron_indicator"]["value"] is None
    assert measures["lend_neutron_indicator"]["implemented"] is False
    assert measures["slope"]["available"] is None
    assert measures["earth_visibility"]["status"] == "not_implemented"
    assert all(item["used_in_similarity"] is None for item in measures.values())
    for source in first["sources"].values():
        assert all(len(item["sha256"]) == 64 for item in source["files"])
    destination = tmp_path / "result.json"
    write_document(first, destination)
    assert json.loads(destination.read_text(encoding="utf-8")) == first
    with pytest.raises(FileExistsError):
        write_document(second, destination)


def test_pending_inside_coverage_has_unknown_availability(metadata_pair, registry_path):
    sites = [{"id": "test", "is_example": True, "latitude_deg": 0, "longitude_deg": 0}]
    result = build_document(metadata_pair, sites, read_json(registry_path))
    measurement = result["sites"][0]["measurements"]["rock_abundance"]
    assert measurement["available"] is None
    assert measurement["within_declared_latitude_bounds"] is True


def test_strict_json_and_protected_inputs(tmp_path):
    destination = tmp_path / "input.xml"
    destination.write_text("original", encoding="utf-8")
    with pytest.raises(ValueError, match="protegida"):
        write_document({}, destination, [destination])
    assert destination.read_text() == "original"
    with pytest.raises(ValueError):
        write_document({"value": float("nan")}, tmp_path / "not_created.json")
    assert not (tmp_path / "not_created.json").exists()
    invalid = tmp_path / "invalid.json"
    invalid.write_text('{"latitude": NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="Constante"):
        read_json(invalid)


@pytest.mark.parametrize("sites", [
    [], [{"id": "x", "latitude_deg": 0, "longitude_deg": 0}],
    [{"id": "x", "is_example": True, "latitude_deg": True, "longitude_deg": 0}],
    [{"id": "x", "is_example": True, "latitude_deg": 91, "longitude_deg": 0}],
    [{"id": "x", "is_example": True, "latitude_deg": "0", "longitude_deg": 0}],
    [{"id": "x", "is_example": True, "latitude_deg": 0, "longitude_deg": 0}] * 2,
])
def test_bad_site_definitions_rejected(sites):
    with pytest.raises(ValueError):
        validate_sites(sites)


def test_registry_cannot_claim_new_processors_or_similarity(registry_path):
    original = read_json(registry_path)
    for field, value in [("implemented", True), ("used_in_similarity", True)]:
        registry = deepcopy(original)
        registry["variables"][2][field] = value
        with pytest.raises(ValueError):
            validate_registry(registry)
