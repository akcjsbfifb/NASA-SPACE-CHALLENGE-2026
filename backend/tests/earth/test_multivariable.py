import pytest

from app.services.earth.multivariable import kelvin_ratio, rank_preselected


def test_kelvin_ratio_sensitivity_and_validity():
    assert [kelvin_ratio(100, earth) for earth in (100, 200, 300, 400)] == pytest.approx([1, .5, 1/3, .25])
    assert kelvin_ratio(100, 300) == kelvin_ratio(300, 100)
    for value in (0, -1, float('nan')):
        with pytest.raises(ValueError): kelvin_ratio(100, value)


def _fixtures():
    search = {'variables_used': [{'id': 'slope', 'weight': 1.0, 'tier': 'A', 'unit': 'deg'}],
              'target': {'slope': 3}, 'points': [
                  {'row_index': 1, 'score_values': {'slope': .9}, 'deltas': {}},
                  {'row_index': 2, 'score_values': {'slope': .5}, 'deltas': {}},
                  {'row_index': 3, 'score_values': {'slope': .7}, 'deltas': {}},
              ]}
    enrichment = [
        {'additional_measurements': {'surface_temperature_modis': {'available': True, 'value': 400}}},
        {'additional_measurements': {'surface_temperature_modis': {'available': True, 'value': 100}}},
        {'additional_measurements': {'surface_temperature_modis': {'available': False, 'reason': 'nodata'}}},
    ]
    return search, enrichment


def test_weights_change_order_and_missing_is_not_zero():
    search, data = _fixtures()
    low = rank_preselected(search, data, {'tbol_modis': 100}, {'tbol_modis': .1})
    high = rank_preselected(search, data, {'tbol_modis': 100}, {'tbol_modis': 1})
    assert low['points'][0]['row_index'] == 1
    assert high['points'][0]['row_index'] == 2
    assert low['points'][0]['effective_weights'] == pytest.approx({'slope': 1 / 1.1, 'tbol_modis': .1 / 1.1})
    assert sum(low['points'][0]['weighted_shares'].values()) == pytest.approx(1)
    missing = next(p for p in high['points'] if p['row_index'] == 3)
    assert missing['coverage'] == 1 and missing['coverage_requested'] == 2
    assert missing['closeness'] == pytest.approx(.7)
    assert 'tbol_modis' not in missing['scores']
    assert missing['effective_weights'] == {'slope': 1}
    strict = rank_preselected(search, data, {'tbol_modis': 100}, {'tbol_modis': 1}, min_coverage=2)
    assert {p['row_index'] for p in strict['points']} == {1, 2}
    assert strict['candidate_generation']['scope'] == 'geometry_preselected_not_global_multivariable'


def test_era5_is_independent_of_modis_and_preserves_missing_status():
    search, data = _fixtures()
    data[0]['additional_measurements']['soil_temperature_0_to_7cm'] = {'available': True, 'value': 200}
    data[1]['additional_measurements']['soil_temperature_0_to_7cm'] = {'available': False, 'reason': 'network_error'}
    result = rank_preselected(search, data, {'treg_era5': 100}, {'treg_era5': .5})
    first = next(p for p in result['points'] if p['row_index'] == 1)
    second = next(p for p in result['points'] if p['row_index'] == 2)
    assert first['scores']['treg_era5'] == .5
    assert first['closeness'] == pytest.approx((.9 + .5 * .5) / 1.5, abs=.0001)
    assert second['comparison_status']['treg_era5']['reason'] == 'network_error'
    assert 'treg_era5' not in second['scores']
