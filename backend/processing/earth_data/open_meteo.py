"""ERA5-Land hourly soil temperature from Open-Meteo; file cache by request."""

import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import urlopen

ENDPOINT = 'https://archive-api.open-meteo.com/v1/archive'
VARIABLE = 'soil_temperature_0_to_7cm'
WARNINGS = ['local_solar_midnight_does_not_guarantee_darkness_at_high_latitudes',
            'soil_layer_0_to_7cm_not_lunar_radiometric_regolith_temperature']


def _key(lat, lon, start, end):
    payload = json.dumps([float(lat), float(lon), start, end, 'era5_land', 'UTC', 'v2'], separators=(',', ':'))
    return hashlib.sha256(payload.encode()).hexdigest()


def _result(data, requested, start, end):
    if data.get('utc_offset_seconds') != 0:
        raise ValueError('La respuesta no confirma UTC')
    if data.get('hourly_units', {}).get(VARIABLE) != '°C':
        raise ValueError('Unidad de temperatura inesperada')
    hourly = data['hourly']
    times, values = hourly['time'], hourly[VARIABLE]
    if len(times) != len(values) or not times:
        raise ValueError('Serie horaria vacía o inconsistente')
    selected = []
    for stamp, value in zip(times, values):
        utc = datetime.fromisoformat(stamp)
        if value is not None and math.isfinite(float(value)):
            # Mean solar time, not a civil timezone: select 00:00 ± 30 min.
            hour = (utc.hour + utc.minute / 60 + requested[1] / 15) % 24
            if min(hour, 24 - hour) <= .5:
                selected.append(float(value))
    average = sum(selected) / len(selected) if selected else None
    return {
        'value': None if average is None else average + 273.15, 'unit': 'K',
        'original_value': average, 'original_unit': '°C',
        'available': average is not None, 'status': 'valid' if average is not None else 'missing',
        'reason': None if average is not None else 'no_valid_local_midnight_hours',
        'source': 'Open-Meteo ERA5-Land', 'model': 'era5_land', 'variable': VARIABLE,
        'requested_coordinates': {'lat': requested[0], 'lon': requested[1]},
        'grid_coordinates': {'lat': data.get('latitude'), 'lon': data.get('longitude')},
        'period_start': start, 'period_end': end, 'timezone': 'UTC',
        'utc_offset_seconds': data['utc_offset_seconds'],
        'method': 'mean of available hours within 30 min of mean local solar midnight; longitude/15',
        'warnings': WARNINGS,
        'selected_hours': len(selected), 'hours_returned': len(times), 'raw_hourly': hourly,
    }


def sample_many(points, start, end, cache_dir, timeout=15, batch_size=20):
    points = list(points)
    datetime.fromisoformat(start); datetime.fromisoformat(end)
    if start > end or not 1 <= batch_size <= 20:
        raise ValueError('Período o tamaño de lote inválido')
    cache = Path(cache_dir); cache.mkdir(parents=True, exist_ok=True)
    unique = []
    for lat, lon in points:
        lat, lon = float(lat), float(lon)
        if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ValueError('Coordenadas terrestres inválidas')
        pair = (lat, lon)
        if pair not in unique: unique.append(pair)
    results, missing = {}, []
    for pair in unique:
        path = cache / (_key(*pair, start, end) + '.json')
        if path.is_file():
            record = json.loads(path.read_text(encoding='utf8'))
            if record.get('request') != [*pair, start, end, 'era5_land', 'UTC']:
                raise ValueError('Metadatos de caché inconsistentes')
            results[pair] = {**record['measurement'], 'warnings': WARNINGS, 'cache_hit': True}
        else: missing.append(pair)
    for offset in range(0, len(missing), batch_size):
        batch = missing[offset:offset + batch_size]
        params = {'latitude': ','.join(str(p[0]) for p in batch), 'longitude': ','.join(str(p[1]) for p in batch),
                  'start_date': start, 'end_date': end, 'hourly': VARIABLE, 'models': 'era5_land', 'timezone': 'GMT'}
        started = time.monotonic()
        try:
            with urlopen(ENDPOINT + '?' + urlencode(params), timeout=timeout) as response:
                body = response.read(2_000_001)
            if len(body) > 2_000_000: raise ValueError('Respuesta demasiado grande')
            payload = json.loads(body)
            payload = payload if isinstance(payload, list) else [payload]
            if len(payload) != len(batch): raise ValueError('La cantidad de respuestas no coincide con las coordenadas')
        except HTTPError as error:
            affected = missing[offset:] if error.code == 429 else batch
            for pair in affected:
                results[pair] = {'value': None, 'unit': 'K', 'available': False, 'status': 'not_sampled',
                                 'reason': 'rate_limited' if error.code == 429 else 'remote_request_failed',
                                 'error': str(error), 'source': 'Open-Meteo ERA5-Land',
                                 'requested_coordinates': {'lat': pair[0], 'lon': pair[1]}, 'cache_hit': False}
            if error.code == 429: break
            continue
        except (OSError, ValueError) as error:
            for pair in batch:
                results[pair] = {'value': None, 'unit': 'K', 'available': False, 'status': 'not_sampled',
                                 'reason': 'remote_request_failed', 'error': str(error), 'source': 'Open-Meteo ERA5-Land',
                                 'requested_coordinates': {'lat': pair[0], 'lon': pair[1]}, 'cache_hit': False}
            continue
        for pair, data in zip(batch, payload):
            try:
                measurement = _result(data, pair, start, end)
            except (KeyError, TypeError, ValueError) as error:
                results[pair] = {'value': None, 'unit': 'K', 'available': False, 'status': 'invalid',
                                 'reason': 'invalid_response', 'error': str(error), 'source': 'Open-Meteo ERA5-Land',
                                 'requested_coordinates': {'lat': pair[0], 'lon': pair[1]}, 'cache_hit': False}
                continue
            measurement['acquired_utc'] = datetime.now(timezone.utc).isoformat()
            measurement['transfer'] = {'batch_bytes': len(body), 'batch_points': len(batch),
                                       'seconds': round(time.monotonic() - started, 3)}
            record = {'request': [*pair, start, end, 'era5_land', 'UTC'], 'measurement': measurement}
            path = cache / (_key(*pair, start, end) + '.json')
            temp = path.with_suffix('.tmp')
            temp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf8')
            temp.replace(path)
            results[pair] = {**measurement, 'cache_hit': False}
    return [results[(float(lat), float(lon))] for lat, lon in points]
