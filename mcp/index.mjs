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
const ACTIVITY_RULES_TEXT = `Pesos: weights es un extra. Si la frase no pide una importancia distinta y no cae en una actividad, no mandes weights. Si cae en una actividad, manda solo activity: todo preset trae valores de búsqueda. Si además nombra un código o un valor, manda ese argumento explícito; pisa al preset solo en esa clave. No inventes números. rock es un código USGS, nunca la palabra basalto. vb es basalto, py es piroclástico, pb es plutónico básico (norita/gabro en este catálogo), su es sedimento suelto.

Primera regla que coincida:
- VIPER o prospectar hielo con un rover: activity viper_ice_prospect.
- Artemis o aterrizaje polar: activity artemis_polar_landing.
- rille o Hadley: activity hadley_rille.
- piroclástico, Shorty o suelo naranja: activity sample_pyroclastic.
- norita, SPA o Chang'e 4: activity spa_norite.
- light mantle, manto claro o avalancha de regolito: activity light_mantle.
- Surveyor o regolito suelto: activity surveyor_regolith.
- rueda o durabilidad de ruedas de un rover: activity rover_wheels.
- hielo polar, trampa de hielo o LCROSS: activity polar_ice.
- basalto de mare o muestrear basalto: activity sample_basalt.
- extraer y analizar el piso, o tipo de piso: activity floor_sample.
- alunizaje, aterrizaje o sitio de aterrizaje: activity landing_site.
Si la frase pide importancia y no coincidió ninguna regla, manda solo las claves de weights que nombró, más los targets que nombró. No rellenes el resto.`;

const SERVER_INSTRUCTIONS = `${FILTER_RULES_TEXT} ${BUSCAR_INSTRUCTIONS} ${ACTIVITY_RULES_TEXT}`;

const shortlistPath = new URL('../data/earth/shortlist.json', import.meta.url);
const filteredPath = new URL('../data/earth/filtered.json', import.meta.url);
const activitiesPath = new URL('./activities.json', import.meta.url);

// The enum comes from the catalog itself; a hand-written list would drift from activities.json.
const ACTIVITY_IDS = JSON.parse(readFileSync(toFsPath(activitiesPath), 'utf8')).map(
  (entry) => entry.id,
);

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

const weightsInputSchema = z
  .strictObject({
    slope: z
      .number()
      .min(0)
      .max(1)
      .optional()
      .describe('Relative importance of slope, 0–1. Omit to keep the preset value.'),
    roughness: z
      .number()
      .min(0)
      .max(1)
      .optional()
      .describe('Relative importance of roughness, 0–1. Omit to keep the preset value.'),
    temperature: z
      .number()
      .min(0)
      .max(1)
      .optional()
      .describe('Relative importance of coldest-month temperature, 0–1. Omit to keep it.'),
    ice: z
      .number()
      .min(0)
      .max(1)
      .optional()
      .describe('Relative importance of ice thickness, 0–1. Omit to keep the preset value.'),
    rock: z
      .number()
      .min(0)
      .max(1)
      .optional()
      .describe('Relative importance of rock type, 0–1. Omit to keep the preset value.'),
  })
  .optional()
  .describe(
    'Per-request importance overrides. Send only the keys the phrase named; the preset fills the rest. Python decides, this schema only validates.',
  );

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
  activity: z
    .enum(ACTIVITY_IDS)
    .optional()
    .describe(
      'Activity preset id from mcp/activities.json. The preset supplies the search values; send no numbers with it unless the phrase named one.',
    ),
  weights: weightsInputSchema,
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
  const body = {
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
  // Carry the search inputs the shortlist already holds so listar does not lose them.
  if (shortlist.activity !== undefined) body.activity = shortlist.activity;
  if (shortlist.weights !== undefined) body.weights = shortlist.weights;
  return body;
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
  for (const key of [
    'slope',
    'roughness',
    'tmin',
    'ice',
    'rock',
    'precision',
    'activity',
    'weights',
  ]) {
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

export {
  ACTIVITY_IDS,
  buildBuscarPayload,
  buscarInputSchema,
  buscarWithWorker,
  GurvichSearchWorker,
};

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
