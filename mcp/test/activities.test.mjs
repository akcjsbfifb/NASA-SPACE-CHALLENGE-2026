import assert from 'node:assert/strict';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { pathToFileURL } from 'node:url';
import {
  ACTIVITY_IDS,
  SERVER_INSTRUCTIONS,
  buildBuscarPayload,
  buscarInputSchema,
  limpiarFiltros,
} from '../index.mjs';

const catalog = JSON.parse(readFileSync(new URL('../activities.json', import.meta.url), 'utf8'));

// Catalog order, as written in the spec. The instructions block lists the ids in rule order.
const CATALOG_IDS = [
  'rover_wheels',
  'landing_site',
  'polar_ice',
  'sample_basalt',
  'floor_sample',
  'viper_ice_prospect',
  'artemis_polar_landing',
  'sample_pyroclastic',
  'spa_norite',
  'hadley_rille',
  'surveyor_regolith',
  'light_mantle',
];

const RULE_ORDER_IDS = [
  'viper_ice_prospect',
  'artemis_polar_landing',
  'hadley_rille',
  'sample_pyroclastic',
  'spa_norite',
  'light_mantle',
  'surveyor_regolith',
  'rover_wheels',
  'polar_ice',
  'sample_basalt',
  'floor_sample',
  'landing_site',
];

test('activities.json has exactly twelve ids in catalog order', () => {
  assert.equal(catalog.length, 12);
  assert.deepEqual(
    catalog.map((entry) => entry.id),
    CATALOG_IDS,
  );
  assert.deepEqual(ACTIVITY_IDS, CATALOG_IDS);
});

test('buildBuscarPayload forwards activity alone and invents no numbers', () => {
  assert.deepEqual(buildBuscarPayload({ activity: 'rover_wheels' }), { activity: 'rover_wheels' });
});

test('buildBuscarPayload forwards weights unchanged and fills no other key', () => {
  const payload = buildBuscarPayload({ weights: { slope: 0.3 } });
  assert.deepEqual(payload, { weights: { slope: 0.3 } });
  assert.deepEqual(Object.keys(payload.weights), ['slope']);
});

test('buildBuscarPayload keeps activity and weights out when absent', () => {
  const payload = buildBuscarPayload({ slope: 5, precision: 0.7 });
  assert.deepEqual(payload, { slope: 5, precision: 0.7 });
  assert.equal('activity' in payload, false);
  assert.equal('weights' in payload, false);
});

test('buscar schema rejects an activity outside the catalog', () => {
  const rejected = buscarInputSchema.safeParse({ activity: 'nope' });
  assert.equal(rejected.success, false);
  assert.equal(buscarInputSchema.safeParse({ activity: 'rover_wheels' }).success, true);
  assert.equal(buscarInputSchema.safeParse({ weights: { slope: 0.3 } }).success, true);
  assert.equal(buscarInputSchema.safeParse({}).success, true);
});

test('SERVER_INSTRUCTIONS carries the twelve rule ids in order and the preset rule', () => {
  assert.match(SERVER_INSTRUCTIONS, /todo preset trae valores de búsqueda/);
  let cursor = -1;
  for (const id of RULE_ORDER_IDS) {
    const at = SERVER_INSTRUCTIONS.indexOf(`activity ${id}.`);
    assert.notEqual(at, -1, `SERVER_INSTRUCTIONS is missing activity ${id}`);
    assert.ok(at > cursor, `activity ${id} is out of order in SERVER_INSTRUCTIONS`);
    cursor = at;
  }
});

test('filtered.json keeps activity and weights copied from the shortlist', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'artemis-activities-'));
  const shortlistPath = pathToFileURL(path.join(dir, 'shortlist.json'));
  const filteredPath = pathToFileURL(path.join(dir, 'filtered.json'));
  const weights = { slope: 0.5, roughness: 1, temperature: 0, ice: 0, rock: 1 };
  try {
    writeFileSync(
      shortlistPath,
      JSON.stringify({
        target: { slope: 8, rock: 'vb' },
        precision: 0.7,
        temperature_mode: 'not_used',
        activity: { id: 'rover_wheels' },
        weights,
        points: [{ lat: 1, lon: 2, closeness: 1 }],
      }),
    );
    const outcome = limpiarFiltros({ shortlistPath, filteredPath });
    assert.equal(outcome.error, undefined);
    const written = JSON.parse(readFileSync(filteredPath, 'utf8'));
    assert.deepEqual(written.activity, { id: 'rover_wheels' });
    assert.deepEqual(written.weights, weights);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
