import { existsSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { McpServer } from '@modelcontextprotocol/server';
import { StdioServerTransport } from '@modelcontextprotocol/server/stdio';
import * as z from 'zod/v4';
import { applyFilters, buildFilterRulesText, validateFilters } from './applyFilters.mjs';
import {
  GurvichSearchWorker,
  buscarWithWorker,
  DEFAULT_PYTHON,
  DEFAULT_WORKER_SCRIPT,
} from './gurvichWorker.mjs';

const FILTER_RULES_TEXT = buildFilterRulesText();
const BUSCAR_INSTRUCTIONS =
  'buscar ejecuta la misma consulta que la UI de búsqueda y escribe data/earth/shortlist.json; no recalcula vía aplicar_filtros. La primera llamada de la sesión puntúa toda la grilla terrestre en memoria; las siguientes reutilizan el proceso persistente. aplicar_filtros no recalcula closeness: solo filtra la shortlist ya escrita.';
const SERVER_INSTRUCTIONS = `${FILTER_RULES_TEXT} ${BUSCAR_INSTRUCTIONS}`;

const shortlistPath = new URL('../data/earth/shortlist.json', import.meta.url);
const filteredPath = new URL('../data/earth/filtered.json', import.meta.url);

const SOURCE = 'data/earth/shortlist.json';

const filterInputSchema = z.object({
  id: z
    .string()
    .describe(
      'Catalog filter id, or a country name. Country names are accepted in English and Spanish (Argentina, Chile, Norway, Islandia). in_country takes the country name in value. in_argentina is the Argentina box with no value. Unknown country names return error unknown_id.',
    ),
  value: z
    .unknown()
    .optional()
    .describe(
      'Filter value. For in_country: country name in English or Spanish. For rock_is: USGS code. For lat_band/lon_band: [min, max]. Omit for in_argentina, outside_famous, and when id itself is a country name.',
    ),
});

const aplicarInputSchema = z.object({
  filters: z.array(filterInputSchema).optional(),
});

const emptyInputSchema = z.object({});

const buscarInputSchema = z.object({
  slope: z.number().optional().describe('Target slope in degrees.'),
  roughness: z.number().optional().describe('Target roughness in metres.'),
  tmin: z.number().optional().describe('Target coldest-month temperature in °C.'),
  ice: z.number().optional().describe('Target ice thickness in metres.'),
  rock: z.string().optional().describe('USGS lithology abbrev (e.g. vb, su).'),
  precision: z
    .number()
    .optional()
    .describe('Shortlist tightness 0–1; default 0.7 like the UI.'),
});

function toFsPath(fileUrl) {
  return fileURLToPath(fileUrl);
}

function jsonResult(body, isError = false) {
  return {
    content: [{ type: 'text', text: JSON.stringify(body) }],
    isError,
  };
}

function errorResult(code) {
  return jsonResult({ error: code }, true);
}

function loadShortlist(fileUrl = shortlistPath) {
  try {
    const parsed = JSON.parse(readFileSync(toFsPath(fileUrl), 'utf8'));
    if (!parsed || !Array.isArray(parsed.points)) return { error: 'bad_shortlist' };
    return { data: parsed };
  } catch {
    return { error: 'bad_shortlist' };
  }
}

function wireRows(rows) {
  return rows.map(({ lat, lon, reason }) => ({ lat, lon, reason }));
}

function buildBody(shortlist, filters, result) {
  const hidden = wireRows(result.hidden);
  const missing = wireRows(result.missing);
  return {
    version: 1,
    source: SOURCE,
    target: shortlist.target,
    precision: shortlist.precision,
    temperature_mode: shortlist.temperature_mode,
    filters,
    returned: result.points.length,
    hidden_count: hidden.length,
    missing_count: missing.length,
    points: result.points,
    hidden,
    missing,
  };
}

export function writeFiltered(body, fileUrl = filteredPath) {
  const dest = toFsPath(fileUrl);
  const tmp = `${dest}.tmp`;
  writeFileSync(tmp, `${JSON.stringify(body, null, 2)}\n`);
  renameSync(tmp, dest);
}

export function aplicarFiltros(filters, paths = { shortlistPath, filteredPath }) {
  const invalid = validateFilters(filters);
  if (invalid) return { error: invalid, wrote: false };
  const loaded = loadShortlist(paths.shortlistPath);
  if (loaded.error) return { error: loaded.error, wrote: false };
  const result = applyFilters(loaded.data.points, filters);
  if (result.error) return { error: result.error, wrote: false };
  const body = buildBody(loaded.data, filters, result);
  writeFiltered(body, paths.filteredPath);
  return { body, wrote: true };
}

export function limpiarFiltros(paths = { shortlistPath, filteredPath }) {
  const loaded = loadShortlist(paths.shortlistPath);
  if (loaded.error) return { error: loaded.error, wrote: false };
  const result = { points: loaded.data.points, hidden: [], missing: [] };
  const body = buildBody(loaded.data, [], result);
  writeFiltered(body, paths.filteredPath);
  return { body, wrote: true };
}

export function listarFiltros(fileUrl = filteredPath) {
  const dest = toFsPath(fileUrl);
  if (!existsSync(dest)) return { error: 'no_filter' };
  const body = JSON.parse(readFileSync(dest, 'utf8'));
  return { body };
}

function buildBuscarPayload(args) {
  const payload = {};
  for (const key of ['slope', 'roughness', 'tmin', 'ice', 'rock', 'precision']) {
    const value = args[key];
    if (value !== undefined && value !== null) payload[key] = value;
  }
  return payload;
}

const BUSCAR_SUMMARY_KEYS = [
  'target',
  'precision',
  'returned',
  'closest',
  'loosest',
  'temperature_mode',
  'variables',
  'frontend_error',
  'shortlist_error',
];

export function summarizeBuscarResult(body) {
  if (!body || typeof body !== 'object') return body;
  if (body.error) return { error: body.error };
  const summary = {};
  for (const key of BUSCAR_SUMMARY_KEYS) {
    if (body[key] !== undefined) summary[key] = body[key];
  }
  if (Array.isArray(body.points)) {
    summary.points = body.points.slice(0, 8);
  }
  return summary;
}

export function createServer(options = {}) {
  const worker =
    options.worker ??
    new GurvichSearchWorker({
      python: options.python ?? DEFAULT_PYTHON,
      script: options.workerScript ?? DEFAULT_WORKER_SCRIPT,
      env: options.workerEnv ?? process.env,
    });

  const server = new McpServer(
    { name: 'gurvich', version: '0.1.0' },
    {
      instructions: SERVER_INSTRUCTIONS,
      maxToolInputElements: 1024,
    },
  );

  server.registerTool(
    'aplicar_filtros',
    {
      title: 'Apply shortlist filters',
      description: `${FILTER_RULES_TEXT} Esta herramienta lee data/earth/shortlist.json, escribe data/earth/filtered.json y no borra data/earth/shortlist.json.`,
      inputSchema: aplicarInputSchema,
      annotations: { destructiveHint: true },
    },
    async ({ filters }) => {
      const outcome = aplicarFiltros(filters);
      if (outcome.error) return errorResult(outcome.error);
      return jsonResult(outcome.body);
    },
  );

  server.registerTool(
    'limpiar_filtros',
    {
      title: 'Clear shortlist filters',
      description: `${FILTER_RULES_TEXT} Esta herramienta reescribe data/earth/filtered.json con filters: [] y todos los puntos visibles; no escribe data/earth/shortlist.json ni lo borra.`,
      inputSchema: emptyInputSchema,
      annotations: { destructiveHint: true },
    },
    async () => {
      const outcome = limpiarFiltros();
      if (outcome.error) return errorResult(outcome.error);
      return jsonResult(outcome.body);
    },
  );

  server.registerTool(
    'listar',
    {
      title: 'List current filter result',
      description: `${FILTER_RULES_TEXT} Esta herramienta solo lee data/earth/filtered.json; no escribe archivos ni borra data/earth/shortlist.json.`,
      inputSchema: emptyInputSchema,
      annotations: { readOnlyHint: true },
    },
    async () => {
      const outcome = listarFiltros();
      if (outcome.error) return errorResult(outcome.error);
      return jsonResult(outcome.body);
    },
  );

  const buscarDescription = `${BUSCAR_INSTRUCTIONS} Escribe data/earth/shortlist.json. No recalcula closeness con aplicar_filtros.`;

  server.registerTool(
    'buscar',
    {
      title: 'Search Earth analogs (UI query)',
      description: buscarDescription,
      inputSchema: buscarInputSchema,
      annotations: { destructiveHint: true },
    },
    async (args) => {
      const payload = buildBuscarPayload(args);
      let body;
      try {
        body = await buscarWithWorker(worker, payload);
      } catch (error) {
        return errorResult(error?.message ?? String(error));
      }
      if (body && typeof body === 'object' && body.error) return errorResult(body.error);
      return jsonResult(summarizeBuscarResult(body));
    },
  );

  return server;
}

export { buildBuscarPayload, buscarWithWorker, GurvichSearchWorker };

async function main() {
  const server = createServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

const thisFile = fileURLToPath(import.meta.url);
const invoked = process.argv[1] ? path.resolve(process.argv[1]) : '';
if (invoked === thisFile) {
  main().catch((error) => {
    process.stderr.write(`${error?.stack ?? error}\n`);
    process.exit(1);
  });
}

export { shortlistPath, filteredPath, SERVER_INSTRUCTIONS };
