"""Small WCS 2.0 subsets of SoilGrids cfvo, in its native Homolosine CRS."""

import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import urlopen

import rasterio
from rasterio.io import MemoryFile
from rasterio.warp import transform

BASE = 'https://maps.isric.org/mapserv'
COVERAGE = 'cfvo_0-5cm_mean'
NATIVE = '+proj=igh +datum=WGS84 +units=m +no_defs'
CRS_URI = 'http://www.opengis.net/def/crs/EPSG/0/152160'


def _request(params, timeout, limit):
    url = BASE + '?' + urlencode(params, doseq=True)
    with urlopen(url, timeout=timeout) as response:
        data = response.read(limit + 1)
        content_type = response.headers.get('Content-Type', '')
    if len(data) > limit: raise ValueError('Respuesta WCS excede el límite')
    return data, content_type


def inspect_service(timeout=15):
    common = [('map', '/map/cfvo.map'), ('SERVICE', 'WCS'), ('VERSION', '2.0.0')]
    capabilities, _ = _request(common + [('REQUEST', 'GetCapabilities')], timeout, 1_000_000)
    description, _ = _request(common + [('REQUEST', 'DescribeCoverage'), ('COVERAGEID', COVERAGE)], timeout, 1_000_000)
    if COVERAGE.encode() not in capabilities or COVERAGE.encode() not in description:
        raise ValueError('La cobertura cfvo no figura en los metadatos')
    return {'capabilities_xml': capabilities.decode('utf8'), 'description_xml': description.decode('utf8')}


def sample(lat, lon, cache_dir, timeout=15):
    lat, lon = float(lat), float(lon)
    if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError('Coordenadas terrestres inválidas')
    xs, ys = transform('EPSG:4326', NATIVE, [lon], [lat])
    x, y = xs[0], ys[0]
    if not (-19949750 <= x <= 19861750 and -6147500 <= y <= 8361000):
        return {'value': None, 'unit': '1', 'raw_value': None, 'raw_unit': 'cm3/dm3',
                'available': False, 'status': 'not_sampled', 'reason': 'outside_declared_wcs_extent',
                'source': 'ISRIC SoilGrids 2.0', 'coverage': COVERAGE,
                'coordinates': {'lat': lat, 'lon': lon}, 'cache_hit': False}
    cache = Path(cache_dir); cache.mkdir(parents=True, exist_ok=True)
    # Fixed native-CRS tiles let nearby candidate points share a single request.
    tile_x = math.floor((x + 19949750) / 1000)
    tile_y = math.floor((y + 6147500) / 1000)
    xmin, ymin = -19949750 + tile_x * 1000, -6147500 + tile_y * 1000
    key = hashlib.sha256(json.dumps([tile_x, tile_y, COVERAGE, 'tile_v1'], separators=(',', ':')).encode()).hexdigest()
    path, manifest = cache / (key + '.tif'), cache / (key + '.json')
    hit = path.is_file() and manifest.is_file()
    if hit:
        body = path.read_bytes(); meta = json.loads(manifest.read_text(encoding='utf8'))
        if hashlib.sha256(body).hexdigest() != meta['sha256']:
            raise ValueError('Hash del recorte WCS no coincide')
    else:
        params = [('map','/map/cfvo.map'), ('SERVICE','WCS'), ('VERSION','2.0.1'),
                  ('REQUEST','GetCoverage'), ('COVERAGEID',COVERAGE), ('FORMAT','image/tiff'),
                  ('SUBSET',f'X({xmin:.3f},{xmin+1000:.3f})'), ('SUBSET',f'Y({ymin:.3f},{ymin+1000:.3f})'),
                  ('SUBSETTINGCRS',CRS_URI), ('OUTPUTCRS',CRS_URI)]
        started = time.monotonic()
        body, kind = _request(params, timeout, 2_000_000)
        if not (body.startswith(b'II*\x00') or body.startswith(b'MM\x00*')):
            raise ValueError('WCS no devolvió GeoTIFF: ' + kind + ' ' + body[:200].decode('utf8', errors='replace'))
        meta = {'sha256': hashlib.sha256(body).hexdigest(), 'acquired_utc': datetime.now(timezone.utc).isoformat(),
                'transfer_bytes': len(body), 'transfer_seconds': round(time.monotonic() - started, 3),
                'requested_coordinates': [lat, lon], 'coverage': COVERAGE, 'crs': CRS_URI}
        path.write_bytes(body); manifest.write_text(json.dumps(meta, indent=2), encoding='utf8')
    with MemoryFile(body) as memory, memory.open() as ds:
        if ds.crs is None: raise ValueError('El GeoTIFF WCS no declara CRS')
        xout, yout = transform('EPSG:4326', ds.crs, [lon], [lat])
        row, col = ds.index(xout[0], yout[0])
        if not (0 <= row < ds.height and 0 <= col < ds.width): raise ValueError('Coordenada fuera del recorte')
        cell = ds.read(1, window=((row, row+1), (col, col+1)), masked=True)[0, 0]
        masked = bool(getattr(cell, 'mask', False))
        value = None if masked else float(cell)
        nodata = ds.nodata
        # This WCS emits zero on open ocean with no declared nodata or mask.
        # Zero may also be a real prediction; treat it as ambiguous, never as a measurement.
        ambiguous_zero = value == 0 and nodata is None
        valid = value is not None and math.isfinite(value) and 0 <= value <= 1000 and not ambiguous_zero
        pixel = {'row': row, 'column': col, 'transform': list(ds.transform)[:6], 'crs': ds.crs.to_string()}
    return {'value': value / 1000 if valid else None, 'unit': '1', 'raw_value': value,
            'raw_unit': 'cm3/dm3', 'volume_percent': value / 10 if valid else None,
            'available': valid, 'status': 'valid' if valid else 'missing',
            'reason': None if valid else ('zero_ambiguous_no_nodata_mask' if ambiguous_zero else 'nodata_or_outside_physical_range'),
            'source': 'ISRIC SoilGrids 2.0', 'coverage': COVERAGE, 'coordinates': {'lat': lat, 'lon': lon},
            'quality': {'nodata': nodata, 'note': 'WCS DescribeCoverage does not declare nil values'},
            'pixel': pixel, 'cache_hit': hit, 'acquired_utc': meta['acquired_utc'], 'sha256': meta['sha256'],
            'transfer': {'bytes': meta.get('transfer_bytes', len(body)), 'seconds': meta.get('transfer_seconds')}}


def sample_many(points, cache_dir, timeout=15, min_interval=1.0):
    """Nearby coordinates reuse cached one-kilometre WCS tiles."""
    points = list(points)
    results = []
    last_request = None
    for index, (lat, lon) in enumerate(points):
        try:
            if last_request is not None:
                remaining = min_interval - (time.monotonic() - last_request)
                if remaining > 0: time.sleep(remaining)
            result = sample(lat, lon, cache_dir, timeout)
            results.append(result)
            if not result.get('cache_hit') and result.get('reason') != 'outside_declared_wcs_extent':
                last_request = time.monotonic()
        except HTTPError as error:
            if error.code == 429:
                for p_lat, p_lon in points[index:]:
                    results.append({'value': None, 'unit': '1', 'available': False, 'status': 'not_sampled',
                                    'reason': 'wcs_rate_limited', 'coordinates': {'lat': p_lat, 'lon': p_lon},
                                    'source': 'ISRIC SoilGrids 2.0'})
                break
            last_request = time.monotonic()
            results.append({'value': None, 'unit': '1', 'available': False, 'status': 'not_sampled',
                            'reason': 'wcs_request_failed', 'error': str(error),
                            'coordinates': {'lat': lat, 'lon': lon}, 'source': 'ISRIC SoilGrids 2.0'})
        except (OSError, ValueError) as error:
            last_request = time.monotonic()
            results.append({'value': None, 'unit': '1', 'available': False, 'status': 'not_sampled',
                            'reason': 'wcs_request_failed', 'error': str(error),
                            'coordinates': {'lat': lat, 'lon': lon}, 'source': 'ISRIC SoilGrids 2.0'})
    return results
