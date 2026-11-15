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
