import assert from 'node:assert/strict';
import { existsSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { applyFilters, validateFilters } from '../applyFilters.mjs';
import { points } from './fixture.mjs';

const filteredPath = fileURLToPath(new URL('../../data/earth/filtered.json', import.meta.url));

function visibleIds(result) {
  return result.points.map((point) => point.id);
}

function tagged(rows) {
  return rows.map((row) => `${row.id ?? `${row.lat},${row.lon}`}/${row.reason}`);
}

function diskStamp() {
  if (!existsSync(filteredPath)) return { exists: false, mtimeMs: null };
  return { exists: true, mtimeMs: statSync(filteredPath).mtimeMs };
}

function assertNoDiskTouch(before) {
  const after = diskStamp();
  assert.deepEqual(after, before);
}

function assertUnchanged(inputPoints, inputFilters, run) {
  const pointsBefore = structuredClone(inputPoints);
  const filtersBefore = structuredClone(inputFilters);
  const result = run();
  assert.deepEqual(inputPoints, pointsBefore);
  assert.deepEqual(inputFilters, filtersBefore);
  return result;
}

test('fixture imports without reading disk', () => {
  assert.equal(points.length, 4);
  assert.deepEqual(
    points.map((point) => point.id),
    ['puna', 'atacama', 'svalbard', 'dry_valley'],
  );
});

test('AC-01: no filters keeps all four points in order', () => {
  const result = applyFilters(points, []);
  assert.equal(result.error, undefined);
  assert.deepEqual(visibleIds(result), ['puna', 'atacama', 'svalbard', 'dry_valley']);
  assert.deepEqual(result.hidden, []);
  assert.deepEqual(result.missing, []);
});

test('AC-02: in_argentina keeps puna and atacama', () => {
  const result = applyFilters(points, [{ id: 'in_argentina' }]);
  assert.deepEqual(visibleIds(result), ['puna', 'atacama']);
});

test('AC-03: in_argentina and max_tmin_c=0', () => {
  const result = applyFilters(points, [
    { id: 'in_argentina' },
    { id: 'max_tmin_c', value: 0 },
  ]);
  assert.deepEqual(visibleIds(result), ['puna']);
  assert.deepEqual(tagged(result.hidden), [
    'atacama/fail:tmin_c',
    'svalbard/fail:lat',
    'dry_valley/fail:lat',
  ]);
});

test('AC-04: max_tmin_c=0 splits hidden and missing', () => {
  const result = applyFilters(points, [{ id: 'max_tmin_c', value: 0 }]);
  assert.deepEqual(visibleIds(result), ['puna', 'svalbard']);
  assert.deepEqual(tagged(result.hidden), ['atacama/fail:tmin_c']);
  assert.deepEqual(tagged(result.missing), ['dry_valley/missing:tmin_c']);
});

test('AC-05: outside_famous keeps puna and svalbard', () => {
  const result = applyFilters(points, [{ id: 'outside_famous' }]);
  assert.deepEqual(visibleIds(result), ['puna', 'svalbard']);
  assert.deepEqual(tagged(result.hidden), ['atacama/fail:lat', 'dry_valley/fail:lat']);
});

test('AC-06: rock_is=vb', () => {
  const result = applyFilters(points, [{ id: 'rock_is', value: 'vb' }]);
  assert.deepEqual(visibleIds(result), ['puna', 'svalbard']);
});

test('AC-07: min_ice_m=100', () => {
  const result = applyFilters(points, [{ id: 'min_ice_m', value: 100 }]);
  assert.deepEqual(visibleIds(result), ['dry_valley']);
});

test('AC-08: min_closeness=0.8', () => {
  const result = applyFilters(points, [{ id: 'min_closeness', value: 0.8 }]);
  assert.deepEqual(visibleIds(result), ['puna', 'svalbard']);
});

test('AC-09: lat_band=[-40,-20]', () => {
  const result = applyFilters(points, [{ id: 'lat_band', value: [-40, -20] }]);
  assert.deepEqual(visibleIds(result), ['puna', 'atacama']);
});

test('AC-10: max_slope_deg=6', () => {
  const result = applyFilters(points, [{ id: 'max_slope_deg', value: 6 }]);
  assert.deepEqual(visibleIds(result), ['atacama', 'dry_valley']);
});

test('AC-11: min_score_temperature uses tmin_c null as missing', () => {
  const result = applyFilters(points, [{ id: 'min_score_temperature', value: 0.75 }]);
  assert.equal(
    result.missing.some((row) => row.id === 'dry_valley' && row.reason === 'missing:tmin_c'),
    true,
  );
  assert.equal(result.hidden.some((row) => row.id === 'dry_valley'), false);
  assert.equal(result.points.some((point) => point.id === 'dry_valley'), false);
});

test('AC-12: in_argentina with value is unexpected_value and skips disk', () => {
  const before = diskStamp();
  const filters = [{ id: 'in_argentina', value: 1 }];
  const result = applyFilters(points, filters);
  assert.deepEqual(result, { error: 'unexpected_value' });
  assert.equal(result.points, undefined);
  assertNoDiskTouch(before);
});

test('AC-13: rock_is=basalt is bad_rock', () => {
  const before = diskStamp();
  const result = applyFilters(points, [{ id: 'rock_is', value: 'basalt' }]);
  assert.deepEqual(result, { error: 'bad_rock' });
  assertNoDiskTouch(before);
});

test('AC-14: empty filters is empty_filters for validateFilters', () => {
  const before = diskStamp();
  assert.equal(validateFilters([]), 'empty_filters');
  assert.equal(validateFilters(undefined), 'empty_filters');
  assertNoDiskTouch(before);
});

test('AC-15: duplicate id is duplicate_id and skips disk', () => {
  const before = diskStamp();
  const result = applyFilters(points, [
    { id: 'in_argentina' },
    { id: 'in_argentina' },
  ]);
  assert.deepEqual(result, { error: 'duplicate_id' });
  assertNoDiskTouch(before);
});

test('AC-16: applyFilters does not mutate points or filters', () => {
  const filters = [{ id: 'in_argentina' }, { id: 'max_tmin_c', value: 0 }];
  const result = assertUnchanged(points, filters, () => applyFilters(points, filters));
  assert.deepEqual(visibleIds(result), ['puna']);
});

test('in_country Argentina keeps puna and atacama', () => {
  const result = applyFilters(points, [{ id: 'in_country', value: 'Argentina' }]);
  assert.deepEqual(visibleIds(result), ['puna', 'atacama']);
});

test('in_country Noruega keeps svalbard', () => {
  const result = applyFilters(points, [{ id: 'in_country', value: 'Noruega' }]);
  assert.deepEqual(visibleIds(result), ['svalbard']);
  assert.deepEqual(tagged(result.hidden), [
    'puna/fail:lat',
    'atacama/fail:lat',
    'dry_valley/fail:lat',
  ]);
});

test('country name as id keeps the same Argentina box', () => {
  const result = applyFilters(points, [{ id: 'argentina' }]);
  assert.deepEqual(visibleIds(result), ['puna', 'atacama']);
});

test('unknown country name is unknown_id and skips disk', () => {
  const before = diskStamp();
  const result = applyFilters(points, [{ id: 'in_country', value: 'Narnia' }]);
  assert.deepEqual(result, { error: 'unknown_id' });
  assert.equal(result.points, undefined);
  assertNoDiskTouch(before);
});

test('unknown country id is unknown_id', () => {
  const result = applyFilters(points, [{ id: 'narnia' }]);
  assert.deepEqual(result, { error: 'unknown_id' });
});
