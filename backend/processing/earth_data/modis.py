"""Point sampling of the MOD11C3.061 monthly HDF4 product."""

import calendar
import math
import re
from datetime import datetime, timedelta
from pathlib import Path

from pyhdf.SD import SD, SDC

LAYERS = ("LST_Night_CMG", "QC_Night", "Night_view_time", "Clear_sky_nights")


class ModisMonthly:
    def __init__(self, path):
        self.path = Path(path)
        match = re.fullmatch(r"MOD11C3\.A(\d{4})(\d{3})\.061\.\d+\.hdf", self.path.name)
        if not match:
            raise ValueError("Se requiere un archivo MOD11C3 colección 061")
        self.start = datetime(int(match[1]), 1, 1) + timedelta(days=int(match[2]) - 1)
        if self.start.day != 1 or self.start.year != int(match[1]):
            raise ValueError("El archivo mensual debe comenzar el primer día del mes")
        self.data = None
        self.layers = {}

    def __enter__(self):
        self.data = SD(str(self.path), SDC.READ)
        try:
            attrs = self.data.attributes()
            if attrs.get('identifier_product_doi') != '10.5067/MODIS/MOD11C3.061':
                raise ValueError('El DOI del HDF no corresponde a MOD11C3.061')
            if (self.path.name not in attrs.get('CoreMetadata.0', '') or
                    'GCTP_GEO' not in attrs.get('StructMetadata.0', '')):
                raise ValueError('Identidad o grilla geográfica HDF inesperada')
            if not set(LAYERS).issubset(self.data.datasets()):
                raise ValueError("Faltan capas MOD11C3 requeridas")
            for name in LAYERS:
                layer = self.data.select(name)
                self.layers[name] = layer
                if tuple(layer.info()[2]) != (3600, 7200):
                    raise ValueError("Dimensiones MOD11C3 inesperadas")
            lst = self.layers['LST_Night_CMG'].attributes()
            view = self.layers['Night_view_time'].attributes()
            if (lst.get('units') != 'K' or lst.get('_FillValue') != 0 or
                    lst.get('valid_range') != [7500, 65535] or lst.get('scale_factor') != .02 or
                    lst.get('add_offset') != 0 or view.get('_FillValue') != 255 or view.get('scale_factor') != .2):
                raise ValueError('Escala o constantes MOD11C3 inesperadas')
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *args):
        for layer in self.layers.values():
            layer.endaccess()
        self.layers.clear()
        if self.data is not None:
            self.data.end()
            self.data = None

    def sample(self, lat, lon):
        if self.data is None:
            raise RuntimeError("Abrir el archivo con un contexto")
        lat, lon = float(lat), float(lon)
        if not math.isfinite(lat) or not math.isfinite(lon) or not -90 <= lat <= 90:
            raise ValueError("Coordenadas terrestres inválidas")
        signed_lon = (lon + 180) % 360 - 180
        row = min(int(math.floor((90 - lat) * 20)), 3599)
        col = min(int(math.floor((signed_lon + 180) * 20)), 7199)
        raw = {name: int(layer.get(start=(row, col), count=(1, 1))[0, 0]) for name, layer in self.layers.items()}
        quality = raw['QC_Night']
        # Conservative policy: NASA mandatory quality 00 and good L1B quality bit 2.
        days = calendar.monthrange(self.start.year, self.start.month)[1]
        clear = (raw['Clear_sky_nights'] & ((1 << days) - 1)).bit_count()
        reason = None
        if raw['LST_Night_CMG'] == 0:
            reason = 'pds_fill_value'
        elif not 7500 <= raw['LST_Night_CMG'] <= 65535:
            reason = 'outside_valid_range'
        elif quality & 3 != 0 or quality & 4 != 0:
            reason = 'quality_rejected'
        elif clear == 0:
            reason = 'no_clear_nights'
        valid = reason is None
        view = raw['Night_view_time']
        return {
            'value': raw['LST_Night_CMG'] * .02 if valid else None, 'unit': 'K',
            'available': valid, 'status': 'valid' if valid else 'missing',
            'reason': reason,
            'source': 'NASA MODIS Terra MOD11C3.061', 'file_name': self.path.name,
            'period_start': self.start.date().isoformat(),
            'period_end': (self.start + timedelta(days=days-1)).date().isoformat(),
            'coordinates_requested': {'lat': lat, 'lon': lon},
            'pixel': {'row': row, 'column': col, 'center_lat': 90-(row+.5)/20,
                      'center_lon': -180+(col+.5)/20, 'degrees_per_pixel': .05},
            'raw': raw, 'raw_unit': 'MOD11C3 integer counts', 'scale': .02, 'offset': 0.0,
            'quality': {'mandatory_qa': quality & 3, 'data_quality': (quality >> 2) & 1,
                        'terra_aqua_combined': (quality >> 3) & 1, 'emissivity_flag': (quality >> 4) & 3,
                        'lst_error_flag': (quality >> 6) & 3, 'clear_sky_nights_count': clear,
                        'night_view_time_utc_hour': view * .2 if 0 <= view <= 120 else None,
                        'policy': 'mandatory_qa_00_and_data_quality_good_and_at_least_one_clear_night'},
        }

    def sample_many(self, points):
        return [self.sample(lat, lon) for lat, lon in points]
