import { existsSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { McpServer } from '@modelcontextprotocol/server';
import { StdioServerTransport } from '@modelcontextprotocol/server/stdio';
import * as z from 'zod/v4';
import { applyFilters, validateFilters } from './applyFilters.mjs';

const SERVER_INSTRUCTIONS =
  'Filtrás la shortlist ya buscada. No recalculás closeness. No inventás celdas. No movés el mapa. Si tmin_c es null, lo decís como dato faltante.';

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

export function createServer() {
  const server = new McpServer(
    { name: 'analog-filter', version: '0.1.0' },
    {
      instructions: SERVER_INSTRUCTIONS,
      maxToolInputElements: 1024,
    },
  );

  server.registerTool(
    'aplicar_filtros',
    {
      title: 'Apply shortlist filters',
      description:
        'Apply one or more catalog filters to data/earth/shortlist.json and write data/earth/filtered.json. Does not recalculate closeness. To keep only one country, use { "id": "in_country", "value": "<country name>" } or { "id": "<country name>" }. Names: English or Spanish (Argentina, Chile, Norway, Islandia). Unknown names return {"error":"unknown_id"}. in_argentina remains valid (Argentina box, no value). Other catalog ids: lat_band, lon_band, max_slope_deg, min_slope_deg, max_roughness_m, min_roughness_m, max_tmin_c, min_tmin_c, max_ice_m, min_ice_m, rock_is, min_closeness, max_closeness, min_score_slope, min_score_roughness, min_score_temperature, min_score_ice, min_score_rock, outside_famous.',
      inputSchema: aplicarInputSchema,
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
      description:
        'Write data/earth/filtered.json with an empty filters array and every shortlist point visible.',
      inputSchema: emptyInputSchema,
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
      description:
        'Read data/earth/filtered.json without writing. Returns no_filter when that file does not exist.',
      inputSchema: emptyInputSchema,
    },
    async () => {
      const outcome = listarFiltros();
      if (outcome.error) return errorResult(outcome.error);
      return jsonResult(outcome.body);
    },
  );

  return server;
}

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
