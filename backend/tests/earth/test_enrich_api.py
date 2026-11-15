import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

pytest.importorskip('pyhdf')
pytest.importorskip('rasterio')

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend' / 'processing'))
from app.main import app
import earth_data.enrich
from app.services import search_state


def test_enrichment_response_is_additive_and_does_not_return_hourly_series(monkeypatch):
    def fake(candidates, *args, **kwargs):
        assert candidates == [{'lat': 1.0, 'lon': 2.0}]
        return {'ranking_changed': False, 'scope': 'preselected', 'candidates': [{
            **candidates[0], 'additional_measurements': {
                'soil_temperature_0_to_7cm': {'value': 280, 'raw_hourly': {'time': ['x']}},
            }}]}
    monkeypatch.setattr(earth_data.enrich, 'enrich_candidates', fake)
    with TestClient(app) as client:
        response = client.post('/enrich', json={'candidates': [{'lat': 1, 'lon': 2}]})
    assert response.status_code == 200
    data = response.json()
    assert data['ranking_changed'] is False
    assert data['candidates'][0]['additional_measurements']['soil_temperature_0_to_7cm'] == {'value': 280}


def test_enrichment_bounds_candidate_count():
    with TestClient(app) as client:
        response = client.post('/enrich', json={'candidates': [{'lat': 0, 'lon': 0}] * 51})
    assert response.status_code == 422


def test_thermal_only_is_explicitly_unsupported(monkeypatch, tiny_index):
    monkeypatch.setattr(search_state, '_index', tiny_index)
    with TestClient(app) as client:
        response = client.get('/search', params={'tbol_modis': 100, 'w_tbol_modis': 1})
    assert response.status_code == 400
    assert response.json()['error'] == 'unsupported_candidate_generation'


def test_no_positive_weight_reports_unavailable(monkeypatch, tiny_index):
    monkeypatch.setattr(search_state, '_index', tiny_index)
    with TestClient(app) as client:
        response = client.get('/search', params={'slope': 8, 'w_slope': 0})
    assert response.status_code == 400
    assert response.json()['scoring_status'] == 'not_available'


def test_lunar_candidate_limit_is_applied_without_changing_general_search(monkeypatch, tiny_index, tmp_path):
    monkeypatch.setattr(search_state, '_index', tiny_index)
    from app.services.earth import similarity
    monkeypatch.setattr(similarity, 'SHORTLIST', tmp_path / 'shortlist.json')
    with TestClient(app) as client:
        limited = client.get('/search', params={'slope': 8, 'candidate_limit': 1})
        invalid = client.get('/search', params={'slope': 8, 'candidate_limit': 51})
    assert limited.status_code == 200
    assert limited.json()['returned'] == len(limited.json()['points']) <= 1
    assert invalid.status_code == 400


def test_multivariable_reorders_disclosed_candidates(monkeypatch, tiny_index, tmp_path):
    monkeypatch.setattr(search_state, '_index', tiny_index)
    from app.services.earth import similarity
    monkeypatch.setattr(similarity, 'SHORTLIST', tmp_path / 'shortlist.json')
    def fake(candidates, *args, **kwargs):
        return {'candidates': [dict(candidate, additional_measurements={
            'surface_temperature_modis': {'available': True, 'value': 100 if candidate['lat'] == 10 else 300},
            'soil_temperature_0_to_7cm': {'available': False, 'value': None, 'reason': 'source_not_selected'},
        }) for candidate in candidates]}
    monkeypatch.setattr(earth_data.enrich, 'enrich_candidates', fake)
    with TestClient(app) as client:
        response = client.get('/search', params={'slope': 8, 'w_slope': .2, 'tbol_modis': 100, 'w_tbol_modis': .8})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['candidate_generation']['scope'] == 'geometry_preselected_not_global_multivariable'
    assert data['candidate_generation']['variables'] == ['slope']
    assert set(data['variables']) == {'slope', 'tbol_modis'}
    assert all(0 <= point['scores']['tbol_modis'] <= 1 for point in data['points'])
