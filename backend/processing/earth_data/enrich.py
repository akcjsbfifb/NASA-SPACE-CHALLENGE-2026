"""Enrich preselected terrestrial candidates without modifying their ranking."""

from pathlib import Path

from .modis import ModisMonthly
from .open_meteo import sample_many as temperatures
from .soilgrids import sample_many as coarse_fragments


def enrich_candidates(candidates, modis_path, start, end, cache_root, *, limit=200):
    candidates = list(candidates)
    if not 1 <= limit <= 200 or len(candidates) > limit:
        raise ValueError('El enriquecimiento admite hasta 200 candidatos preseleccionados')
    coordinates = [(float(item['lat']), float(item['lon'])) for item in candidates]
    cache_root = Path(cache_root)
    try:
        with ModisMonthly(modis_path) as modis:
            modis_values = modis.sample_many(coordinates)
    except Exception as error:
        modis_values = [{'value': None, 'unit': 'K', 'available': False, 'status': 'not_sampled',
                         'reason': 'modis_source_unavailable', 'error': str(error)} for _ in candidates]
    try:
        soil_values = temperatures(coordinates, start, end, cache_root / 'era5_land')
    except (OSError, ValueError) as error:
        soil_values = [{'value': None, 'unit': 'K', 'available': False, 'status': 'not_sampled',
                        'reason': 'era5_source_unavailable', 'error': str(error)} for _ in candidates]
    fragments = coarse_fragments(coordinates, cache_root / 'soilgrids')
    results = []
    for candidate, modis_value, soil_value, fragment in zip(candidates, modis_values, soil_values, fragments):
        results.append({**candidate, 'additional_measurements': {
            'surface_temperature_modis': modis_value,
            'soil_temperature_0_to_7cm': soil_value,
            'coarse_fragments_0_to_5cm': fragment,
        }})
    return {'scope': 'enrichment_of_preselected_candidates_not_global_multivariable_search',
            'ranking_changed': False, 'candidates': results}
