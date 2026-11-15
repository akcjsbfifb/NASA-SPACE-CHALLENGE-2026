"""Exploratory scoring of a disclosed, geometry-preselected candidate set."""

import math

from app.services.earth.similarity import grade_for, match_for


THERMAL_SOURCES = {
    'tbol_modis': ('surface_temperature_modis', 'MODIS MOD11C3.061'),
    'treg_era5': ('soil_temperature_0_to_7cm', 'ERA5-Land via Open-Meteo'),
}


def kelvin_ratio(lunar, earth):
    """Relative temperature ratio on the absolute Kelvin scale, not equivalence."""
    lunar, earth = float(lunar), float(earth)
    if not math.isfinite(lunar) or not math.isfinite(earth) or lunar <= 0 or earth <= 0:
        raise ValueError('Both Kelvin temperatures must be positive and finite')
    return min(lunar, earth) / max(lunar, earth)


def rank_preselected(search, enrichment, thermal_targets, thermal_weights, min_coverage=1):
    """Re-rank only supplied candidates; no score is fabricated for missing data."""
    if len(search['points']) != len(enrichment):
        raise ValueError('Las mediciones no corresponden a la selección de candidatos')
    geometry = search['variables_used']
    selected = [v['id'] for v in geometry] + list(thermal_targets)
    if not 1 <= min_coverage <= len(selected):
        raise ValueError('Cobertura mínima fuera del rango seleccionado')
    results = []
    for point, extra in zip(search['points'], enrichment):
        scores = dict(point.get('score_values', {}))
        weights = {v['id']: float(v['weight']) for v in geometry}
        statuses = {}
        additional = extra.get('additional_measurements', {})
        for name, target in thermal_targets.items():
            key, _ = THERMAL_SOURCES[name]
            measurement = additional.get(key, {})
            valid = measurement.get('available') is True and measurement.get('value') is not None
            if valid:
                try:
                    scores[name] = kelvin_ratio(target, measurement['value'])
                except (TypeError, ValueError):
                    valid = False
            statuses[name] = {'available': valid, 'reason': None if valid else measurement.get('reason') or 'invalid_temperature'}
            weights[name] = thermal_weights[name]
        available = {name: score for name, score in scores.items() if name in selected and weights.get(name, 0) > 0}
        weight_sum = sum(weights[name] for name in available)
        if len(available) < min_coverage or weight_sum <= 0:
            continue
        value = sum(score * weights[name] for name, score in available.items()) / weight_sum
        weighted_total = sum(score * weights[name] for name, score in available.items())
        shares = {name: score * weights[name] / weighted_total for name, score in available.items()} if weighted_total > 0 else {}
        effective_weights = {name: weights[name] / weight_sum for name in available}
        deltas = dict(point.get('deltas', {}))
        for name, target in thermal_targets.items():
            key, _ = THERMAL_SOURCES[name]
            if name in available:
                deltas[name] = abs(target - additional[key]['value'])
        item = dict(point)
        item.update(additional_measurements=additional, score_values=available,
                    scores={key: round(value, 3) for key, value in available.items()},
                    closeness=round(value, 4), coverage=len(available),
                    coverage_requested=len(selected), scoring_status='valid',
                    comparison_status=statuses, match=match_for(value), grade=grade_for(value),
                    grades={key: grade_for(score) for key, score in available.items()}, weighted_shares=shares,
                    effective_weights=effective_weights,
                    worst=round(min(available.values()), 4), deltas=deltas,
                    _rank_exact=value)
        results.append(item)
    results.sort(key=lambda item: item['_rank_exact'], reverse=True)
    for item in results:
        del item['_rank_exact']
    output = dict(search)
    output.update(points=results, returned=len(results),
                  closest=max((p['closeness'] for p in results), default=None),
                  loosest=min((p['closeness'] for p in results), default=None),
                  target={**search['target'], **thermal_targets},
                  variables=selected,
                  variables_used=geometry + [{'id': name, 'tier': 'C', 'weight': thermal_weights[name], 'unit': 'K'} for name in thermal_targets],
                  weights={**search.get('weights', {}), **thermal_weights},
                  candidate_generation={'scope': 'geometry_preselected_not_global_multivariable',
                      'variables': [v['id'] for v in geometry], 'evaluated': len(enrichment),
                      'universe': 'top candidates from existing geometric search',
                      'limitation': 'places excluded by the geometry prefilter cannot be recovered',
                      'minimum_coverage': min_coverage},
                  scoring_method={'thermal': 'min(lunar_K,earth_K)/max(lunar_K,earth_K)',
                      'interpretation': 'exploratory relative absolute-temperature index; not physical equivalence',
                      'period': '2025-01', 'weights': {**{v['id']: v['weight'] for v in geometry}, **thermal_weights}})
    return output
