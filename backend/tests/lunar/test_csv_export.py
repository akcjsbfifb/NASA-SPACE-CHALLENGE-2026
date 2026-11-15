"""CSV como vista fiel del JSON; ninguna prueba CSV requiere datasets NASA."""

from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from lunar_data.csv_export import export_csv, main


@pytest.fixture
def example_json(repo_root):
    return repo_root / "data/moon/lola_measurements.example.json"


def read_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def save_document(document, path):
    path.write_text(json.dumps(document, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    return path


def test_every_example_csv_cell_matches_json_and_is_reproducible(example_json, tmp_path, repo_root):
    before = example_json.read_bytes()
    document = json.loads(before)
    first, second = tmp_path / "first.csv", tmp_path / "second.csv"
    export_csv(example_json, first)
    export_csv(example_json, second)
    assert first.read_bytes() == second.read_bytes()
    assert example_json.read_bytes() == before
    assert b"\r" not in first.read_bytes()
    rows = read_rows(first)
    assert len(rows) == len(document["sites"])
    for site, row in zip(document["sites"], rows):
        assert row["site_id"] == site["id"]
        assert float(row["latitude_deg"]) == site["requested_coordinates"]["latitude_deg"]
        assert float(row["longitude_deg"]) == site["requested_coordinates"]["longitude_deg"]
        assert row["source_json_file"] == example_json.name
        assert row["source_json_sha256"] == hashlib.sha256(before).hexdigest()
        for variable, column in [("elevation", "elevation_m"), ("roughness", "roughness_m"), ("slope", "slope_deg")]:
            measurement = site["measurements"][variable]
            assert float(row[column]) == measurement["value"]  # sin aproximación ni redondeo
            assert row[f"{variable}_status"] == measurement["status"]
            assert row[f"{variable}_available"] == "true"
            assert row[f"{variable}_reason"] == (measurement["reason"] or "")
        assert len(row) == 17
    # La ubicación austral conserva -10°, sin reemplazarla por 350°.
    assert float(rows[1]["longitude_deg"]) == -10
    published = repo_root / "data/moon/lola_measurements.example.csv"
    assert published.read_bytes() == first.read_bytes()


@pytest.mark.parametrize("status,available,reason", [
    ("missing", False, "non_finite_raw_value"),
    ("invalid", False, "invalid_input"),
    ("not_sampled", False, "exact_pole_not_sampled_longitude_is_degenerate"),
    ("not_implemented", None, "processor_not_implemented"),
    ("not_implemented", False, "outside_declared_latitude_coverage"),
    ("excluded", None, "outside_current_analysis"),
])
def test_unavailable_values_are_blank_with_original_states(example_json, tmp_path, status, available, reason):
    document = json.loads(example_json.read_bytes())
    for site in document["sites"]:
        for variable in ("elevation", "roughness", "slope"):
            site["measurements"][variable].update(value=None, status=status, available=available, reason=reason)
    source = save_document(document, tmp_path / "input.json")
    output = tmp_path / "output.csv"
    export_csv(source, output)
    for row in read_rows(output):
        for variable, column in [("elevation", "elevation_m"), ("roughness", "roughness_m"), ("slope", "slope_deg")]:
            assert row[column] == ""
            assert row[f"{variable}_status"] == status
            assert row[f"{variable}_available"] == ("" if available is None else "false")
            assert row[f"{variable}_reason"] == reason


def test_zero_negative_values_and_csv_quoting(example_json, tmp_path):
    document = json.loads(example_json.read_bytes())
    site = document["sites"][0]
    site["id"] = 'Región, "prueba"\nlunar'
    site["measurements"]["slope"]["value"] = 0
    site["measurements"]["roughness"]["value"] = 0.0
    site["measurements"]["elevation"]["value"] = -123.45678901234567
    source = save_document(document, tmp_path / "input.json")
    output = tmp_path / "output.csv"
    export_csv(source, output)
    row = read_rows(output)[0]
    assert row["site_id"] == site["id"]
    assert row["slope_deg"] == "0"
    assert row["roughness_m"] == "0.0"
    assert float(row["elevation_m"]) == site["measurements"]["elevation"]["value"]


@pytest.mark.parametrize("change", [
    {"unit": "km"}, {"available": True, "value": None},
    {"available": False}, {"status": "missing"}, {"value": True},
    {"value": "0.5"}, {"available": 1}, {"status": ""}, {"reason": 4},
])
def test_contradictory_or_invalid_measurements_rejected(example_json, tmp_path, change):
    document = json.loads(example_json.read_bytes())
    document["sites"][0]["measurements"]["elevation"].update(change)
    source = save_document(document, tmp_path / "input.json")
    output = tmp_path / "output.csv"
    with pytest.raises(ValueError):
        export_csv(source, output)
    assert not output.exists()


@pytest.mark.parametrize("kind", ["schema", "body", "duplicate", "absent_measurement", "absent_available",
    "absent_value", "latitude", "longitude", "empty_sites", "bad_coordinates"])
def test_invalid_documents_rejected_before_creating_output(example_json, tmp_path, kind):
    document = json.loads(example_json.read_bytes())
    site = document["sites"][0]
    if kind == "schema": document["schema_version"] = "99.0.0"
    elif kind == "body": document["coordinate_reference"]["body"] = "Earth"
    elif kind == "duplicate": document["sites"].append(deepcopy(site))
    elif kind == "absent_measurement": del site["measurements"]["slope"]
    elif kind == "absent_available": del site["measurements"]["slope"]["available"]
    elif kind == "absent_value": del site["measurements"]["slope"]["value"]
    elif kind == "latitude": site["requested_coordinates"]["latitude_deg"] = 91
    elif kind == "longitude": site["requested_coordinates"]["longitude_deg"] = False
    elif kind == "empty_sites": document["sites"] = []
    elif kind == "bad_coordinates": site["requested_coordinates"] = None
    source = save_document(document, tmp_path / "input.json")
    with pytest.raises(ValueError):
        export_csv(source, tmp_path / "not_created.csv")
    assert not (tmp_path / "not_created.csv").exists()


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity", "1e999"])
def test_nonfinite_values_rejected(example_json, tmp_path, constant):
    document = json.loads(example_json.read_bytes())
    original = document["sites"][0]["measurements"]["slope"]["value"]
    source = tmp_path / "bad.json"
    source.write_text(json.dumps(document).replace(str(original), constant), encoding="utf-8")
    with pytest.raises(ValueError):
        export_csv(source, tmp_path / "not_created.csv")
    assert not (tmp_path / "not_created.csv").exists()


def test_protected_input_and_existing_output(example_json, tmp_path):
    original = example_json.read_bytes()
    with pytest.raises(ValueError, match="entrada"):
        export_csv(example_json, example_json)
    existing = tmp_path / "existing.csv"
    existing.write_text("preserve", encoding="utf-8")
    with pytest.raises(FileExistsError):
        export_csv(example_json, existing)
    assert existing.read_text() == "preserve"
    with pytest.raises(ValueError, match=".json"):
        export_csv(tmp_path / "ldem.img", tmp_path / "new.csv")
    assert example_json.read_bytes() == original


def test_cli_uses_only_json_without_scientific_dependencies(example_json, tmp_path, repo_root):
    output = tmp_path / "from_other_directory.csv"
    # -I -S impide utilizar dependencias instaladas o el checkout como cwd.
    # El guard permite abrir exclusivamente el JSON fuente y el CSV de salida.
    code = '''
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from lunar_data.csv_export import main
source, output = Path(sys.argv[2]), Path(sys.argv[3])
allowed = {source.resolve(), output.resolve()}
original_open = Path.open
opened = []
def guarded_open(self, *args, **kwargs):
    assert self.resolve() in allowed, "Unexpected file read: " + str(self)
    opened.append(self.resolve())
    return original_open(self, *args, **kwargs)
Path.open = guarded_open
assert main(['--input', str(source), '--output', str(output)]) == 0
assert opened == [source.resolve(), output.resolve()]
assert not any(name in sys.modules for name in ['numpy', 'pvl', 'lunar_data.lola', 'lunar_data.metadata', 'lunar_data.export'])
'''
    result = subprocess.run([sys.executable, "-I", "-S", "-c", code,
        str(repo_root / "backend/processing"), str(example_json), str(output)],
        cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert len(read_rows(output)) == 2


def test_cli_reports_invalid_json_without_output(tmp_path):
    source = tmp_path / "invalid.json"
    source.write_text("{", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        main(["--input", str(source), "--output", str(tmp_path / "missing.csv")])
    assert error.value.code == 2
    assert not (tmp_path / "missing.csv").exists()
