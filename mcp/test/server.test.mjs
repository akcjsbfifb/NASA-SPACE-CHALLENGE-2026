import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import {
  InMemoryTransport,
  LATEST_PROTOCOL_VERSION,
} from '@modelcontextprotocol/server';
import { getCountryBox } from '../countries.mjs';
import {
  aplicarFiltros,
  createServer,
  filteredPath,
  listarFiltros,
  limpiarFiltros,
  shortlistPath,
} from '../index.mjs';

const filteredFs = fileURLToPath(filteredPath);
const shortlistFs = fileURLToPath(shortlistPath);
const mcpDir = fileURLToPath(new URL('..', import.meta.url));

function inArgentinaBox(point) {
  return (
    point.lat >= -55.06 &&
    point.lat <= -21.78 &&
    point.lon >= -73.57 &&
    point.lon <= -53.63
  );
}

function backupFiltered() {
  if (!existsSync(filteredFs)) return { existed: false, text: null };
  return { existed: true, text: readFileSync(filteredFs, 'utf8') };
}

function restoreFiltered(backup) {
  if (backup.existed) writeFileSync(filteredFs, backup.text);
  else if (existsSync(filteredFs)) rmSync(filteredFs);
  if (existsSync(`${filteredFs}.tmp`)) rmSync(`${filteredFs}.tmp`);
}

function parseToolJson(result) {
  assert.equal(result.result.content[0].type, 'text');
  return JSON.parse(result.result.content[0].text);
}

async function withClient(run) {
  const server = createServer();
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
      const timer = setTimeout(() => reject(new Error(`timeout waiting for ${method}`)), 4000);
      pending.set(id, (message) => {
        clearTimeout(timer);
        resolve(message);
      });
      clientSide.send({ jsonrpc: '2.0', id, method, params }).catch(reject);
    });
  try {
    const init = await rpc(1, 'initialize', {
      protocolVersion: LATEST_PROTOCOL_VERSION,
      capabilities: {},
      clientInfo: { name: 'contract-test', version: '0.0.0' },
    });
    await clientSide.send({ jsonrpc: '2.0', method: 'notifications/initialized' });
    return await run({ rpc, init, clientSide });
  } finally {
    await clientSide.close();
    await serverSide.close();
  }
}

const backup = backupFiltered();
test.after(() => restoreFiltered(backup));

test('AC-14: aplicar_filtros with filters [] returns empty_filters and does not write', () => {
  if (existsSync(filteredFs)) rmSync(filteredFs);
  const outcome = aplicarFiltros([]);
  assert.deepEqual(outcome, { error: 'empty_filters', wrote: false });
  assert.equal(existsSync(filteredFs), false);
});

test('AC-17: limpiar_filtros writes empty filters and returned equals shortlist length', () => {
  const shortlist = JSON.parse(readFileSync(shortlistFs, 'utf8'));
  const outcome = limpiarFiltros();
  assert.equal(outcome.error, undefined);
  assert.equal(outcome.body.filters.length, 0);
  assert.equal(outcome.body.returned, shortlist.points.length);
  assert.equal(outcome.body.hidden_count, 0);
  assert.equal(outcome.body.missing_count, 0);
  const written = JSON.parse(readFileSync(filteredFs, 'utf8'));
  assert.equal(written.returned, shortlist.points.length);
  assert.deepEqual(written.filters, []);
  assert.equal(written.points.length, shortlist.points.length);
});

test('AC-18: listar does not change mtime of filtered.json', () => {
  const before = statSync(filteredFs);
  const outcome = listarFiltros();
  assert.equal(outcome.error, undefined);
  const after = statSync(filteredFs);
  assert.equal(after.mtimeMs, before.mtimeMs);
});

test('listar without filtered.json returns no_filter and does not create it', () => {
  if (existsSync(filteredFs)) rmSync(filteredFs);
  const outcome = listarFiltros();
  assert.deepEqual(outcome, { error: 'no_filter' });
  assert.equal(existsSync(filteredFs), false);
});

test('aplicar_filtros in_country Norway keeps only points inside the Norway box', () => {
  const shortlist = JSON.parse(readFileSync(shortlistFs, 'utf8'));
  const norwayBox = getCountryBox('Norway');
  const outcome = aplicarFiltros([{ id: 'in_country', value: 'Norway' }]);
  assert.equal(outcome.error, undefined);
  assert.ok(outcome.body.returned <= shortlist.returned);
  for (const point of outcome.body.points) {
    assert.equal(
      point.lat >= norwayBox.latMin &&
        point.lat <= norwayBox.latMax &&
        point.lon >= norwayBox.lonMin &&
        point.lon <= norwayBox.lonMax,
      true,
    );
  }
});

test('aplicar_filtros in_argentina writes a smaller or equal returned and every point is in the box', () => {
  const shortlist = JSON.parse(readFileSync(shortlistFs, 'utf8'));
  const outcome = aplicarFiltros([{ id: 'in_argentina' }]);
  assert.equal(outcome.error, undefined);
  assert.ok(outcome.body.returned <= shortlist.returned);
  for (const point of outcome.body.points) {
    assert.equal(inArgentinaBox(point), true);
  }
  const written = JSON.parse(readFileSync(filteredFs, 'utf8'));
  assert.equal(written.version, 1);
  assert.equal(written.source, 'data/earth/shortlist.json');
  assert.equal(written.hidden_count, written.hidden.length);
  assert.equal(written.missing_count, written.missing.length);
  assert.equal(written.returned, written.points.length);
  assert.match(readFileSync(filteredFs, 'utf8'), /\n$/);
});

test('aplicar_filtros description tells the client that any country name is a filter', async () => {
  await withClient(async ({ rpc }) => {
    const listed = await rpc(2, 'tools/list', {});
    const aplicar = listed.result.tools.find((tool) => tool.name === 'aplicar_filtros');
    assert.match(aplicar.description, /in_country/);
    assert.match(aplicar.description, /English or Spanish/);
    assert.match(aplicar.description, /unknown_id/);
  });
});

test('MCP tools/call aplicar_filtros unknown country is unknown_id isError', async () => {
  if (existsSync(filteredFs)) rmSync(filteredFs);
  await withClient(async ({ rpc }) => {
    const reply = await rpc(3, 'tools/call', {
      name: 'aplicar_filtros',
      arguments: { filters: [{ id: 'in_country', value: 'Narnia' }] },
    });
    assert.equal(reply.result.isError, true);
    assert.deepEqual(parseToolJson(reply), { error: 'unknown_id' });
    assert.equal(existsSync(filteredFs), false);
  });
});

test('MCP initialize and tools/list expose the three catalog tools', async () => {
  await withClient(async ({ rpc, init }) => {
    assert.equal(init.result.serverInfo.name, 'analog-filter');
    assert.equal(init.result.serverInfo.version, '0.1.0');
    assert.equal(
      init.result.instructions,
      'Filtrás la shortlist ya buscada. No recalculás closeness. No inventás celdas. No movés el mapa. Si tmin_c es null, lo decís como dato faltante.',
    );
    const listed = await rpc(2, 'tools/list', {});
    const names = listed.result.tools.map((tool) => tool.name).sort();
    assert.deepEqual(names, ['aplicar_filtros', 'limpiar_filtros', 'listar']);
  });
});

test('MCP tools/call aplicar_filtros empty_filters is isError', async () => {
  if (existsSync(filteredFs)) rmSync(filteredFs);
  await withClient(async ({ rpc }) => {
    const reply = await rpc(3, 'tools/call', {
      name: 'aplicar_filtros',
      arguments: { filters: [] },
    });
    assert.equal(reply.result.isError, true);
    assert.deepEqual(parseToolJson(reply), { error: 'empty_filters' });
    assert.equal(existsSync(filteredFs), false);
  });
});

test('MCP tools/call listar no_filter is isError', async () => {
  if (existsSync(filteredFs)) rmSync(filteredFs);
  await withClient(async ({ rpc }) => {
    const reply = await rpc(4, 'tools/call', {
      name: 'listar',
      arguments: {},
    });
    assert.equal(reply.result.isError, true);
    assert.deepEqual(parseToolJson(reply), { error: 'no_filter' });
  });
});

test('stdio server starts and answers initialize plus tools/list', async () => {
  const child = spawn('node', ['index.mjs'], {
    cwd: mcpDir,
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  let stdout = '';
  const messages = [];
  child.stdout.setEncoding('utf8');
  child.stdout.on('data', (chunk) => {
    stdout += chunk;
    let newline = stdout.indexOf('\n');
    while (newline !== -1) {
      const line = stdout.slice(0, newline).replace(/\r$/, '');
      stdout = stdout.slice(newline + 1);
      if (line.trim()) messages.push(JSON.parse(line));
      newline = stdout.indexOf('\n');
    }
  });
  const waitFor = (id) =>
    new Promise((resolve, reject) => {
      const started = Date.now();
      const tick = () => {
        const found = messages.find((message) => message.id === id);
        if (found) {
          resolve(found);
          return;
        }
        if (Date.now() - started > 4000) {
          reject(new Error(`stdio timeout for id ${id}: ${JSON.stringify(messages)}`));
          return;
        }
        setTimeout(tick, 25);
      };
      tick();
    });
  try {
    child.stdin.write(
      `${JSON.stringify({
        jsonrpc: '2.0',
        id: 1,
        method: 'initialize',
        params: {
          protocolVersion: LATEST_PROTOCOL_VERSION,
          capabilities: {},
          clientInfo: { name: 'stdio-smoke', version: '0.0.0' },
        },
      })}\n`,
    );
    const init = await waitFor(1);
    assert.equal(init.result.serverInfo.name, 'analog-filter');
    child.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' })}\n`);
    child.stdin.write(
      `${JSON.stringify({ jsonrpc: '2.0', id: 2, method: 'tools/list', params: {} })}\n`,
    );
    const listed = await waitFor(2);
    assert.deepEqual(
      listed.result.tools.map((tool) => tool.name).sort(),
      ['aplicar_filtros', 'limpiar_filtros', 'listar'],
    );
  } finally {
    child.stdin.end();
    child.kill();
  }
});
