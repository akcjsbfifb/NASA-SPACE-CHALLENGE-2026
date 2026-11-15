import json
import subprocess
import sys

import pytest

from lunar_data import __main__ as cli


def test_cli_with_small_rasters(metadata_pair, registry_path, tmp_path, monkeypatch):
    def loader(path):
        return metadata_pair[0 if "ldem" in str(path) else 1]
    monkeypatch.setattr(cli, "load_metadata", loader)
    output = tmp_path / "result.json"
    assert cli.main([
        "--latitude", "45", "--longitude", "45", "--example",
        "--registry", str(registry_path), "--output", str(output),
    ]) == 0
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["sites"][0]["is_example"] is True
    assert result["sites"][0]["measurements"]["elevation"]["value"] == -1250
    assert result["sites"][0]["measurements"]["roughness"]["value"] == 0.25


@pytest.mark.parametrize("arguments", [
    ["--latitude", "0"], ["--sites", "sites.json", "--longitude", "0"],
    ["--sites", "sites.json", "--example"],
])
def test_cli_rejects_ambiguous_or_incomplete_arguments(arguments, tmp_path):
    with pytest.raises(SystemExit) as error:
        cli.main(arguments + ["--output", str(tmp_path / "result.json")])
    assert error.value.code == 2


def test_cli_never_overwrites_existing_output(tmp_path):
    output = tmp_path / "existing.json"
    output.write_text("preserve", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        cli.main(["--latitude", "0", "--longitude", "0", "--output", str(output)])
    assert error.value.code == 2
    assert output.read_text() == "preserve"


@pytest.mark.local_data
def test_cli_real_batch(data_root, registry_path, sites_path, repo_root, tmp_path):
    if not (data_root / "ldem/ldem_16_float.img").exists():
        pytest.skip("Datos locales no incluidos en Git")
    output = tmp_path / "real_batch.json"
    completed = subprocess.run([
        sys.executable, "-m", "lunar_data", "--sites", str(sites_path),
        "--data-root", str(data_root), "--registry", str(registry_path),
        "--output", str(output),
    ], cwd=repo_root, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    document = json.loads(output.read_text(encoding="utf-8"))
    assert len(document["sites"]) == 2
    assert all(site["is_example"] for site in document["sites"])
    equator = document["sites"][0]["measurements"]
    assert equator["elevation"]["value"] == pytest.approx(-718.6850309371948)
    assert equator["roughness"]["value"] == pytest.approx(0.4296111762523651)
    # Los defaults deben funcionar desde otro cwd y el script debe delegar al
    # mismo paquete; no se mantiene una implementación en la ruta anterior.
    default_output = tmp_path / "default_paths.json"
    repeated = subprocess.run([
        sys.executable, str(repo_root / "backend/scripts/extract_moon.py"),
        "--sites", str(sites_path), "--output", str(default_output),
    ], cwd=tmp_path, capture_output=True, text=True)
    assert repeated.returncode == 0, repeated.stderr
    assert json.loads(default_output.read_text(encoding="utf-8"))["sites"] == document["sites"]
