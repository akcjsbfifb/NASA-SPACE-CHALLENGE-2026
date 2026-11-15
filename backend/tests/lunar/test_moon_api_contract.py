import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend" / "scripts"))
from moon_sites import MEASURED, MoonSites
from serve_search import MoonSampler
import serve_search


def test_apollo_payload_contains_seven_real_measurements():
    sites = MoonSites()
    for site in ("apollo-11", "apollo-17"):
        result = sites.find(site)
        assert set(result["measurements"]) == set(MEASURED)
        assert all(value["status"] == "valid" for value in result["measurements"].values())
        assert result["compared"] == []
        assert result["measurements"]["bolometric_temperature"]["unit"] == "K"
        assert result["measurements"]["regolith_temperature"]["unit"] == "K"


def test_free_point_keeps_local_data_when_diviner_is_unavailable(monkeypatch):
    raw = ROOT / "NASA-Lunar-Studies" / "data" / "raw"
    if not (raw / "lola" / "ldem" / "ldem_16_float.img").is_file():
        pytest.skip("local LOLA originals unavailable")
    monkeypatch.setenv("LUNAR_DATA_ROOT", str(raw / "lola"))
    monkeypatch.setenv("LUNAR_HYDROGEN_ROOT", str(raw / "lunar_prospector" / "hydrogen"))
    monkeypatch.delenv("LUNAR_DIVINER_REMOTE", raising=False)
    sampler = MoonSampler()
    normal = sampler.sample(12.3, 45.6)
    assert normal["measurements"]["elevation"]["available"]
    assert normal["measurements"]["hydrogen_abundance_ppm"]["available"]
    assert normal["measurements"]["rock_abundance"]["reason"] == "source_not_configured"
    polar = sampler.sample(-85, -10)
    for name in ("rock_abundance", "bolometric_temperature", "regolith_temperature"):
        assert polar["measurements"][name]["reason"] == "outside_declared_latitude_coverage"
    assert polar["measurements"]["elevation"]["available"]


def test_remote_failure_does_not_hide_other_measurements(monkeypatch):
    raw = ROOT / "NASA-Lunar-Studies" / "data" / "raw"
    if not (raw / "lola" / "ldem" / "ldem_16_float.img").is_file():
        pytest.skip("local LOLA originals unavailable")
    monkeypatch.setenv("LUNAR_DATA_ROOT", str(raw / "lola"))
    monkeypatch.setenv("LUNAR_HYDROGEN_ROOT", str(raw / "lunar_prospector" / "hydrogen"))
    monkeypatch.setenv("LUNAR_DIVINER_REMOTE", "1")
    def unavailable(*args, **kwargs):
        raise OSError("network unavailable")
    monkeypatch.setattr(serve_search, "DivinerRaster", unavailable)
    result = MoonSampler().sample(12.3, 45.6)
    assert result["measurements"]["slope"]["available"]
    assert result["measurements"]["hydrogen_abundance_ppm"]["available"]
    assert result["measurements"]["rock_abundance"]["reason"] == "source_unavailable"
