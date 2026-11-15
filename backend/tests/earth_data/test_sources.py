import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
pytest.importorskip('pyhdf')
pytest.importorskip('rasterio')
import rasterio
from rasterio.io import MemoryFile
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend' / 'processing'))
from earth_data.modis import ModisMonthly
from earth_data.open_meteo import sample_many
from earth_data.soilgrids import sample as soil_sample, NATIVE
from earth_data.enrich import enrich_candidates


class Cell:
    def __init__(self, value): self.value = value
    def get(self, **kwargs): return np.array([[self.value]])


def test_modis_scales_qa_and_clear_night_bits():
    product = ModisMonthly('MOD11C3.A2025001.061.2025035172114.hdf')
    product.data = object()
    product.layers = {k: Cell(v) for k, v in {'LST_Night_CMG': 15000, 'QC_Night': 0,
                                                'Night_view_time': 10, 'Clear_sky_nights': 5}.items()}
    good = product.sample(0, 0)
    assert good['value'] == 300.0
    assert good['quality']['clear_sky_nights_count'] == 2
    assert good['quality']['night_view_time_utc_hour'] == 2
    product.layers['QC_Night'] = Cell(1)
    assert product.sample(0, 0)['value'] is None
    product.layers['QC_Night'] = Cell(0)
    product.layers['LST_Night_CMG'] = Cell(0)
    assert not product.sample(0, 0)['available']


def test_open_meteo_caches_and_converts_local_midnight(tmp_path):
    data = {'latitude': 0, 'longitude': 0, 'utc_offset_seconds': 0, 'hourly_units': {'soil_temperature_0_to_7cm': '°C'},
            'hourly': {'time': ['2025-01-01T00:00', '2025-01-01T12:00'],
                       'soil_temperature_0_to_7cm': [10.0, 30.0]}}
    response = io.BytesIO(json.dumps(data).encode())
    with patch('earth_data.open_meteo.urlopen', return_value=response) as fetch:
        item = sample_many([(0, 0), (0, 0)], '2025-01-01', '2025-01-01', tmp_path)
        assert item[0]['value'] == pytest.approx(283.15)
        assert item[0]['original_value'] == 10
        assert fetch.call_count == 1
    with patch('earth_data.open_meteo.urlopen', side_effect=AssertionError('unexpected request')):
        assert sample_many([(0, 0)], '2025-01-01', '2025-01-01', tmp_path)[0]['cache_hit']


def test_soilgrids_zero_without_mask_is_ambiguous(tmp_path):
    with MemoryFile() as mem:
        with mem.open(driver='GTiff', width=4, height=4, count=1, dtype='int16',
                      crs=NATIVE, transform=from_origin(-500, 500, 250, 250)) as raster:
            raster.write(np.zeros((1, 4, 4), dtype='int16'))
        body = mem.read()
    with patch('earth_data.soilgrids._request', return_value=(body, 'image/tiff')) as fetch:
        result = soil_sample(0, 0, tmp_path)
        assert not result['available']
        assert result['raw_value'] == 0
        assert result['reason'] == 'zero_ambiguous_no_nodata_mask'
        assert soil_sample(0, 0, tmp_path)['cache_hit']
        assert fetch.call_count == 1


def test_local_modis_original_if_available():
    path = ROOT / 'data/raw/earth/modis/MOD11C3.A2025001.061.2025035172114.hdf'
    if not path.exists(): pytest.skip('MODIS original no disponible')
    with ModisMonthly(path) as product:
        item = product.sample(-85, 0)
    assert item['available'] and item['value'] == pytest.approx(245.86)


def test_enrichment_preserves_order_scores_and_other_sources(tmp_path):
    candidates = [{'lat': 1, 'lon': 2, 'closeness': .8, 'scores': {'slope': .7}}]
    temperature = [{'value': 280, 'unit': 'K', 'available': True}]
    fragments = [{'value': None, 'unit': '1', 'available': False}]
    with patch('earth_data.enrich.temperatures', return_value=temperature), \
         patch('earth_data.enrich.coarse_fragments', return_value=fragments):
        result = enrich_candidates(candidates, tmp_path / 'missing.hdf', '2025-01-01', '2025-01-31', tmp_path)
    row = result['candidates'][0]
    assert not result['ranking_changed']
    assert row['closeness'] == .8 and row['scores'] == {'slope': .7}
    assert row['additional_measurements']['soil_temperature_0_to_7cm']['value'] == 280
    assert row['additional_measurements']['surface_temperature_modis']['value'] is None
