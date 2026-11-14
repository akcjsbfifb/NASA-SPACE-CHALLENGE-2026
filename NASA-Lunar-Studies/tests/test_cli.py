import json
import subprocess
import sys

import pytest

from lunar_data import __main__ as cli


def test_cli_with_small_rasters(metadata_pair, module_root, tmp_path, monkeypatch):
    def loader(path):
        return metadata_pair[0 if "ldem" in str(path) else 1]
    monkeypatch.setattr(cli, "load_metadata", loader)
    output = tmp_path / "result.json"
    assert cli.main([
        "--latitude", "45", "--longitude", "45", "--example",
        "--registry", str(module_root / "config/variables.json"), "--output", str(output),
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
def test_cli_real_batch(module_root, tmp_path):
    if not (module_root / "data/raw/lola/ldem/ldem_16_float.img").exists():
        pytest.skip("Datos locales no incluidos en Git")
    output = tmp_path / "real_batch.json"
    completed = subprocess.run([
        sys.executable, "-m", "lunar_data", "--sites", "config/sites.example.json",
        "--output", str(output),
    ], cwd=module_root, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    document = json.loads(output.read_text(encoding="utf-8"))
    assert len(document["sites"]) == 2
    assert all(site["is_example"] for site in document["sites"])
    equator = document["sites"][0]["measurements"]
    assert equator["elevation"]["value"] == pytest.approx(-718.6850309371948)
    assert equator["roughness"]["value"] == pytest.approx(0.4296111762523651)
