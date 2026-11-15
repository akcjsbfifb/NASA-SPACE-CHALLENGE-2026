import assert from 'node:assert/strict';
import test from 'node:test';
import { composeReply } from '../reply.mjs';

const catalog = [
  {
    id: 'rover_wheels',
    serves: { es: 'Probar la durabilidad de las ruedas de un rover en basalto de mare.' },
    voice: {
      profesional: { es: 'Probar la durabilidad de las ruedas de un rover en basalto de mare.' },
      aficionado: { es: 'Ver si las ruedas de un rover aguantan un suelo de roca volcánica como el de los mares de la Luna.' },
    },
  },
];

const body = {
  returned: 178,
  temperature_mode: 'not_used',
  variables: ['slope', 'roughness', 'rock'],
  target: { slope: 8, roughness: 20, rock: 'vb' },
  activity: { id: 'rover_wheels' },
  points: [
    {
      lat: -84.4417,
      lon: -179.375,
      closeness: 0.9708,
      slope_deg: 7.39,
      roughness_m: 20.2,
      rock: '?',
    },
    {
      lat: 1,
      lon: 2,
      closeness: 0.5,
      slope_deg: 1,
      roughness_m: 1,
      rock: 'vb',
    },
  ],
};

const request = { activity: 'rover_wheels' };

test('profesional reply names the closest point and the signed changes', () => {
  const reply = composeReply(body, {
    audience: 'profesional',
    language: 'es',
    request,
    catalog,
  });
  assert.match(reply, /178/);
  assert.match(reply, /-84\.4417/);
  assert.match(reply, /-179\.375/);
  assert.match(reply, /0\.9708/);
  assert.match(reply, /Temperatura y Hielo no entran \(temperature_mode: not_used\)/);
  assert.match(reply, /cambio -0\.61°/);
  assert.match(reply, /cambio \+0\.2 m/);
  assert.match(reply, /celda \?/);
  assert.match(reply, /durabilidad de las ruedas/);
  assert.doesNotMatch(reply, /lat 1/);
});

test('aficionado reply uses the plain voice and the same figures', () => {
  const reply = composeReply(body, {
    audience: 'aficionado',
    language: 'es',
    request,
    catalog,
  });
  assert.match(reply, /roca volcánica/);
  assert.match(reply, /178/);
  assert.match(reply, /0\.9708/);
  assert.match(reply, /0\.61° más plana/);
  assert.match(reply, /0\.2 m por encima/);
  assert.match(reply, /no figura/);
  assert.match(reply, /basalto/);
  assert.match(reply, /Pendiente, objetivo 8°/);
  assert.match(reply, /Rugosidad, objetivo 20 m/);
  assert.match(reply, /Roca, objetivo vb/);
  assert.match(reply, /Temperatura y Hielo no entran/);
  assert.doesNotMatch(reply, /cuesta|irregular del suelo|El frío/);
});
