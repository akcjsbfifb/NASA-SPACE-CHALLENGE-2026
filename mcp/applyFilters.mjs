import { ARGENTINA_BOX, getCountryBox, resolveCountry } from './countries.mjs';

const ROCK_CODES = [
  'su',
  'vb',
  'ss',
  'pb',
  'sm',
  'sc',
  'va',
  'mt',
  'pa',
  'vi',
  'wb',
  'py',
  'pi',
  'ev',
  'nd',
  'ig',
];

const FAMOUS_BOXES = [
  { name: 'atacama', latMin: -25.5, latMax: -22, lonMin: -70, lonMax: -67 },
  { name: 'death_valley', latMin: 36, latMax: 37.2, lonMin: -117.5, lonMax: -116.5 },
  { name: 'iceland', latMin: 63, latMax: 67, lonMin: -25, lonMax: -13 },
  { name: 'hawaii', latMin: 18.5, latMax: 22.5, lonMin: -160.5, lonMax: -154.5 },
  { name: 'haughton', latMin: 75, latMax: 76, lonMin: -90.5, lonMax: -89 },
];

const ANTARCTICA_LAT_MAX = -60;

const FILTERS = {
  in_argentina: { kind: 'in_country', noValue: true, failField: 'lat', country: 'argentina' },
  in_country: { kind: 'in_country', failField: 'lat' },
  lat_band: { kind: 'range', field: 'lat', failField: 'lat' },
  lon_band: { kind: 'range', field: 'lon', failField: 'lon' },
  max_slope_deg: { kind: 'max', field: 'slope_deg' },
  min_slope_deg: { kind: 'min', field: 'slope_deg' },
  max_roughness_m: { kind: 'max', field: 'roughness_m' },
  min_roughness_m: { kind: 'min', field: 'roughness_m' },
  max_tmin_c: { kind: 'max', field: 'tmin_c' },
  min_tmin_c: { kind: 'min', field: 'tmin_c' },
  max_ice_m: { kind: 'max', field: 'ice_thickness_m' },
  min_ice_m: { kind: 'min', field: 'ice_thickness_m' },
  rock_is: { kind: 'rock', field: 'rock' },
  min_closeness: { kind: 'minUnit', field: 'closeness' },
  max_closeness: { kind: 'maxUnit', field: 'closeness' },
  min_score_slope: { kind: 'minUnit', field: 'scores.slope' },
  min_score_roughness: { kind: 'minUnit', field: 'scores.roughness' },
  min_score_temperature: {
    kind: 'minUnit',
    field: 'scores.temperature',
    missingField: 'tmin_c',
  },
  min_score_ice: { kind: 'minUnit', field: 'scores.ice' },
  min_score_rock: { kind: 'minUnit', field: 'scores.rock' },
  outside_famous: { kind: 'outside_famous', noValue: true, failField: 'lat' },
};

function inRect(point, box) {
  return (
    point.lat >= box.latMin &&
    point.lat <= box.latMax &&
    point.lon >= box.lonMin &&
    point.lon <= box.lonMax
  );
}

function inFamousSite(point) {
  if (point.lat <= ANTARCTICA_LAT_MAX) return true;
  return FAMOUS_BOXES.some((box) => inRect(point, box));
}

function readField(point, field) {
  if (field.startsWith('scores.')) {
    const key = field.slice('scores.'.length);
    return point.scores?.[key];
  }
  return point[field];
}

function hasOwnValue(filter) {
  return filter != null && Object.prototype.hasOwnProperty.call(filter, 'value') && filter.value !== undefined;
}

function countrySpec(country) {
  return { kind: 'in_country', noValue: true, failField: 'lat', country };
}

function lookupSpec(id) {
  if (FILTERS[id]) return FILTERS[id];
  const country = resolveCountry(id);
  return country ? countrySpec(country) : null;
}

function validateValue(spec, value) {
  if (spec.kind === 'rock') {
    if (typeof value !== 'string' || !ROCK_CODES.includes(value)) return 'bad_rock';
    return null;
  }
  if (spec.kind === 'in_country') {
    if (typeof value !== 'string' || !resolveCountry(value)) return 'unknown_id';
    return null;
  }
  if (spec.kind === 'range') {
    if (!Array.isArray(value) || value.length !== 2) return 'bad_range';
    if (!Number.isFinite(value[0]) || !Number.isFinite(value[1])) return 'bad_range';
    if (value[0] > value[1]) return 'bad_range';
    return null;
  }
  if (!Number.isFinite(value)) return 'bad_number';
  if ((spec.kind === 'minUnit' || spec.kind === 'maxUnit') && (value < 0 || value > 1)) {
    return 'bad_number';
  }
  return null;
}

function validateFilterEntries(filters) {
  const seen = new Set();
  for (const filter of filters) {
    const id = filter?.id;
    const spec = lookupSpec(id);
    if (!spec) return 'unknown_id';
    if (seen.has(id)) return 'duplicate_id';
    seen.add(id);
    const present = hasOwnValue(filter);
    if (spec.noValue) {
      if (present) return 'unexpected_value';
      continue;
    }
    if (!present) return 'missing_value';
    const valueError = validateValue(spec, filter.value);
    if (valueError) return valueError;
  }
  return null;
}

export function validateFilters(filters) {
  if (!Array.isArray(filters) || filters.length === 0) return 'empty_filters';
  return validateFilterEntries(filters);
}

function missingField(spec) {
  return spec.missingField ?? spec.field;
}

function failField(spec) {
  return spec.failField ?? spec.field;
}

function pointRef(point, reason) {
  const row = { lat: point.lat, lon: point.lon, reason };
  if (point.id !== undefined) row.id = point.id;
  return row;
}

function fieldIsMissing(point, spec) {
  const field = missingField(spec);
  if (!field) return false;
  return readField(point, field) == null;
}

function countryBoxFor(spec, filter) {
  const key = spec.country ?? resolveCountry(filter.value) ?? resolveCountry(filter.id);
  return key ? getCountryBox(key) : null;
}

function predicate(point, filter) {
  const spec = lookupSpec(filter.id);
  switch (spec.kind) {
    case 'in_country': {
      const countryBox = countryBoxFor(spec, filter);
      return countryBox ? inRect(point, countryBox) : false;
    }
    case 'outside_famous':
      return !inFamousSite(point);
    case 'range': {
      const value = readField(point, spec.field);
      return filter.value[0] <= value && value <= filter.value[1];
    }
    case 'max':
    case 'maxUnit':
      return readField(point, spec.field) <= filter.value;
    case 'min':
    case 'minUnit':
      return readField(point, spec.field) >= filter.value;
    case 'rock':
      return readField(point, spec.field) === filter.value;
    default:
      return false;
  }
}

function evaluate(points, filters) {
  const visible = [];
  const hidden = [];
  const missing = [];
  for (const point of points) {
    let bucket = 'visible';
    let reason = null;
    for (const filter of filters) {
      const spec = lookupSpec(filter.id);
      if (fieldIsMissing(point, spec)) {
        bucket = 'missing';
        reason = `missing:${missingField(spec)}`;
        break;
      }
      if (!predicate(point, filter)) {
        bucket = 'hidden';
        reason = `fail:${failField(spec)}`;
        break;
      }
    }
    if (bucket === 'visible') visible.push(point);
    else if (bucket === 'hidden') hidden.push(pointRef(point, reason));
    else missing.push(pointRef(point, reason));
  }
  return { points: visible, hidden, missing };
}

export function applyFilters(points, filters) {
  if (!Array.isArray(filters) || filters.length === 0) {
    return evaluate(points, []);
  }
  const error = validateFilterEntries(filters);
  if (error) return { error };
  return evaluate(points, filters);
}

export { ROCK_CODES, ARGENTINA_BOX, FAMOUS_BOXES, FILTERS, lookupSpec, resolveCountry };
