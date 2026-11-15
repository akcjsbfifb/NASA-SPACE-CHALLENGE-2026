import assert from 'node:assert/strict';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { InMemoryTransport, LATEST_PROTOCOL_VERSION } from '@modelcontextprotocol/server';
import { ArtemisSearchWorker, buscarWithWorker } from '../artemisWorker.mjs';
import { buildBuscarPayload, createServer, summarizeBuscarResult } from '../index.mjs';

const fakeWorkerScript = fileURLToPath(new URL('./fake_artemis_worker.mjs', import.meta.url));

function parseToolJson(result) {
  assert.equal(result.result.content[0].type, 'text');
  return JSON.parse(result.result.content[0].text);
}

async function withClient(server, run) {
  const [clientSide, serverSide] = InMemoryTransport.createLinkedPair();
  const pending = new Map();
  clientSide.onmessage = (message) => {
    if (message.id !== undefined) {
      const resolve = pending.get(message.id);
      if (resolve) {
        pending.delete(message.id);
        resolve(message);
      }
    }
  };
  await server.connect(serverSide);
  await clientSide.start();
  const rpc = (id, method, params) =>
    new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`timeout ${method}`)), 4000);
      pending.set(id, (message) => {
        clearTimeout(timer);
        resolve(message);
      });
      clientSide.send({ jsonrpc: '2.0', id, method, params }).catch(reject);
    });
  try {
    await rpc(1, 'initialize', {
      protocolVersion: LATEST_PROTOCOL_VERSION,
      capabilities: {},
      clientInfo: { name: 'buscar-test', version: '0.0.0' },
    });
    await clientSide.send({ jsonrpc: '2.0', method: 'notifications/initialized' });
    return await run({ rpc });
  } finally {
    await clientSide.close();
    await serverSide.close();
  }
}

test('buildBuscarPayload omits null and undefined', () => {
  assert.deepEqual(buildBuscarPayload({ slope: 5, roughness: null, ice: undefined }), { slope: 5 });
});

test('summarizeBuscarResult keeps at most eight points', () => {
  const points = Array.from({ length: 12 }, (_, i) => ({ lat: i, lon: i }));
  const summary = summarizeBuscarResult({
    returned: 12,
    precision: 0.7,
    target: { slope_deg: 5 },
    closest: { closeness: 0.9 },
    loosest: { closeness: 0.5 },
    temperature_mode: 'single',
    variables: ['slope'],
    points,
  });
  assert.equal(summary.points.length, 8);
  assert.equal(summary.returned, 12);
  assert.deepEqual(summary.target, { slope_deg: 5 });
});

test('buscarWithWorker returns JSON from fake worker', async () => {
  const worker = new ArtemisSearchWorker({
    python: process.execPath,
    script: fakeWorkerScript,
  });
  try {
    const body = await buscarWithWorker(worker, { slope: 3.0, precision: 0.7 });
    assert.equal(body.returned, 2);
    assert.equal(body.points[0].lat, 1.0);
  } finally {
    worker.stop();
  }
});

test('MCP buscar tool forwards fake worker response', async () => {
  const worker = new ArtemisSearchWorker({
    python: process.execPath,
    script: fakeWorkerScript,
  });
  const server = createServer({ worker });
  try {
    await withClient(server, async ({ rpc }) => {
      const reply = await rpc(2, 'tools/call', {
        name: 'buscar',
        arguments: { slope: 10.0, precision: 0.8 },
      });
      assert.notEqual(reply.result.isError, true);
      const body = parseToolJson(reply);
      assert.equal(body.returned, 2);
      assert.equal(body.points.length, 1);
      assert.equal(body.points[0].lat, 1.0);
      assert.equal(body.closest, undefined);
    });
  } finally {
    worker.stop();
  }
});