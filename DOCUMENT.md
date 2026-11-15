# Analog system guide

NASA Space Apps 2026 hackathon product: a 3D globe UI, a FastAPI API, and an MCP stdio server (Artemis) that search for **terrestrial analogs** of a lunar site. Five variables (`slope`, `roughness`, `temperature`, `ice`, `rock`) score already-indexed Earth cells; the map shows the shortlist.

It does not authorize landing. It does not claim physical equivalence between Moon and Earth: ice is an ETOPO proxy, lunar night temperature is not WorldClim `tmin`, and a USGS code is not the lithology of the lunar sample.

## Search walkthrough

From the person to disk, in this order:

1. **Input.** In the UI, hash `#tierra` (manual criteria) or `#luna` (lunar site → `MoonPage.runAnalogSearch`). In MCP, a phrase the model translates into `buscar`.
2. **Resolution.** `activities.resolve` merges the preset (`mcp/activities.json`) with what the request sent: the request overrides only the keys it sends.
3. **Score.** `EarthIndex.search` walks the mmap grid and computes closeness (weighted mean 0–1).
4. **Disk.** `write_shortlist` writes `data/earth/shortlist.json`. `GET /search` always does this; the local MCP worker does too, unless `ARTEMIS_SEARCH_BASE` already returned 200 (then it does not write a local copy: confirmed by `test_worker_uses_remote_search_without_earth_index`).
5. **Optional filters (MCP only).** `aplicar_filtros` reads that shortlist, evaluates already-written points, and writes `data/earth/filtered.json`. It does not recompute closeness.
6. **Map.** The API emits the JSON over SSE (`GET /events`). The UI subscribes; MCP does not paint the globe.

Without mmap columns there is no search: `EarthIndex` requires `data/earth/columns/` and `manifest.json`.

## How to start it (Linux)

Prerequisites: Python 3.12 (`backend/pyproject.toml`: `requires-python = ">=3.12"`) and Node. Two local processes: API on `127.0.0.1:8787`, UI on `127.0.0.1:5173`. MCP is a third one, over stdio; it does not open a port. Those `cd` commands are relative to the repository root, not to a home directory.

**1. Earth columns (once per dataset).** `land_60s.parquet` and `data/earth/columns/` are not in Git (`.gitignore`). `data/earth/columns.json` declares `rows: 82710267`. If the parquet is missing, there is nothing to extract. If the columns are missing, `EarthIndex` fails with `column directory missing` and suggests the command from `rts.toml`.

From `backend/`, with the Makefile venv:

```bash
cd backend
make venv
.venv/bin/python -m app.cli.extract_earth_columns
make dev
```

`make dev` runs `uvicorn app.main:app --host 127.0.0.1 --port 8787`. CORS allows `http://127.0.0.1:5173` and `http://localhost:5173`.

**2. UI**

```bash
cd frontend
npm install
npm run dev
```

Vite listens on `127.0.0.1:5173` and proxies `/api` → `http://127.0.0.1:8787` (the client uses `SEARCH_API = '/api'`).

**3. MCP (separate)**

```bash
cd mcp
npm install
npm start
```

That is `node index.mjs` (stdio). IDE registration: `mcp/README.md`.

There are two venvs. The Makefile creates `backend/.venv`. The MCP worker (`mcp/artemisWorker.mjs`) runs `REPO_ROOT/.venv/bin/python`. If only the Makefile one exists, `buscar` does not start the local index. The API on 8787 avoids that load: the worker forwards to `GET /search`.

The first search of a session loads the grid into RAM; later ones reuse the process.

Environment variables (names; do not paste secrets): `RTS_LOCATION`, `GURVICH_COLUMNS_DIR`, `LUNAR_DATA_ROOT`, `LUNAR_HYDROGEN_ROOT`, `LUNAR_DIVINER_REMOTE`, `GOOGLE_MAPS_API_KEY`, `ARTEMIS_COLUMNS_DIR`, `ARTEMIS_SHORTLIST`, `ARTEMIS_SEARCH_BASE`, `ARTEMIS_NOTIFY_URL`, `ARTEMIS_NOTIFY_TOKEN_PATH`.

## The three doors

### UI

| Hash | What the person does |
|------|---------------------|
| `#tierra` | Five criteria, weights, and `precision`. Search calls `GET /search` **without** `activity`. Lists at most **6** rows (`points.slice(0, 6)`). |
| `#luna` | Picks a site, runs `runAnalogSearch` (`GET /search` with slope/roughness and, if applicable, `tbol_modis` / `treg_era5`) then `POST /enrich`. |

The Earth UI **loads** the catalog (`GET /activities`) for labels; it **does not launch** presets. MCP filters do not exist in React: they do not read `filtered.json`. F5 does not reload the shortlist from disk: on mount it requests history, audience, and catalog, and subscribes to SSE; without a new event, the globe stays empty.

Audience `profesional` \| `aficionado`; languages `es` \| `en` \| `fr` \| `it`. `PUT /audience` writes `data/earth/audience.json`. History: max 50 entries. One enrich job at a time; the second gets 429 `enrichment_busy`. `/scene` uses Google Static Maps if `GOOGLE_MAPS_API_KEY` is present; otherwise Esri World Imagery. The globe heatmap layer panel is commented out in `App.tsx`.

### API

Routes a human uses. The frontend sees them under `/api/...` via the Vite proxy.

| Route | Writes |
|------|---------|
| `GET /search` | `data/earth/shortlist.json` and an SSE event. Thermal path (`tbol_modis` / `treg_era5`): reorders at most 50 already-chosen points. |
| `GET /moon` | Nothing (shows a site or a coordinate). |
| `POST /enrich` | Nothing in the shortlist; adds contextual measurements (MODIS / ERA5 / SoilGrids) to ≤50 candidates. |
| `GET /events` | Nothing (SSE). |
| `POST /notify` | Nothing on disk; re-emits the body over SSE. Header `X-Artemis-Notify-Token`. Token in `output/artemis-notify.token` (`backend/rts.toml`), mode `0600`, regenerated when the API starts. |
| `GET /history` | Nothing (reads). |
| `POST /history` | `data/earth/history.json` (cap 50). |
| `GET /scene` | Nothing (image). |
| `GET /activities` | Nothing (reads `mcp/activities.json`). |
| `GET /cell` | Nothing (nearest cell). |
| `PUT /audience` | `data/earth/audience.json`. |
| `GET /api/v1/health` | Nothing (`{"status": "ok"}`). |

Legacy route or method that does not exist: `404` with `{"error": "not found"}` (also on `POST /search` and `GET /notify`).

### MCP

Four tools. stdio, no port.

| Tool | Disk |
|------|--------|
| `buscar` | Writes `shortlist.json` via the API or, if there is no API, via the local worker. The model gets **at most 8** points (`summarizeBuscarResult`); the globe needs the API and SSE. |
| `aplicar_filtros` | Reads the shortlist, writes `filtered.json`. `filters: []` → `empty_filters` and **does not write**. |
| `limpiar_filtros` | Rewrites `filtered.json` with `filters: []` and all points visible. Does not touch the shortlist. |
| `listar` | Only reads `filtered.json`. If the file does not exist → `no_filter`. |

Validation errors: `unknown_id`, `bad_rock`, `bad_range`, `bad_number`, `duplicate_id`, `unexpected_value`, `missing_value`. Per point, the first failing rule wins: `hidden` with `fail:<field>` or `missing` with `missing:<field>`. `min_score_temperature` looks at `tmin_c` if the score is missing. `rock_is` compares the USGS code (`vb`); `basalt` is `bad_rock`.

## How an analog is chosen

Contract: `data/earth/analogs.json` (`schema_version` `1.0.0`). Five variables:

| id | Score | Parameters |
|----|--------|------------|
| `slope` | `gaussian` | `scale` 8 |
| `roughness` | `gaussian_relative` | `min_scale` 0.25, `ratio` 1.666… |
| `temperature` | `gaussian_temperature` | `scale` 12, `extreme_delta` 15 |
| `ice` | `gaussian_log1p` | `scale` 1.2 |
| `rock` | `categorical` | `same` 1.0, `related` 0.45 |

Query alias: `tmin` → `temperature`. Closeness = weighted mean of the present scores, each in 0–1. A cell with no value **does not enter the denominator** (it does not score zero). `similarity.py` applies `exp(-|Δ|/scale)` in `_decay` on that already-transformed distance.

`precision` (clip 0–1) tightens the cutoff: `min_closeness = 0.55 + 0.35 * precision`. Match labels: ≥ 0.85 `very`, ≥ 0.70 `close`, otherwise `barely`.

There are **12** presets in `mcp/activities.json` (the test `test_catalog_has_the_twelve_presets_in_order` fixes the order): `rover_wheels`, `landing_site`, `polar_ice`, `sample_basalt`, `floor_sample`, `viper_ice_prospect`, `artemis_polar_landing`, `sample_pyroclastic`, `spa_norite`, `hadley_rille`, `surveyor_regolith`, `light_mantle`. The request overrides only the key it sends.

MODIS/ERA5 thermal path: it does not walk the planet. It takes at most 50 points **already** on the shortlist and reorders them; it does not rescue excluded ones. Preselection by `slope` or `roughness` is required.

Rock: USGS code (`vb`), never the word "basalt".

Polar slope: above ~83.81° latitude the point may carry `earth_slope_longitude_distance_clamped_above_83_81_deg`.

## Files that matter

| File | Role | Does a search overwrite it? | Regenerable? |
|---------|-----|------------------------|---------------|
| `data/earth/land_60s.parquet` | Earth grid (ETOPO, WorldClim tmin, GLiM). Git ignores it. | No | Yes, `python -m app.cli.build_earth` (local rasters, not in Git) |
| `data/earth/columns/` | mmap + `manifest.json` | No | Yes, `extract_earth_columns` |
| `data/earth/columns.json` | Metadata and lithology | No | Comes with the build |
| `data/earth/analogs.json` | Score contract | No | By hand |
| `mcp/activities.json` | 12 presets | No | By hand |
| `data/earth/shortlist.json` | Result of `GET /search` / `buscar` | Yes | Regenerated by searching |
| `data/earth/filtered.json` | MCP filter result | Yes, by filters; **not** by a new search | `limpiar_filtros` or filter again |
| `data/earth/history.json` | History (max 50). Git ignores it. | `POST /history` | — |
| `data/earth/audience.json` | Audience and language. Git ignores it. | `PUT /audience` | — |
| `output/artemis-notify.token` | SSE token. Git ignores `output/`. | When the API starts | Regenerates on its own |

## What it does not do

- It does not move `lat`/`lon` or invent cells. Filters cut already-written points.
- `aplicar_filtros` does not recompute closeness.
- `POST /enrich` does not change the geometric ranking. The only thermal reordering is that of `GET /search` with `tbol_modis` / `treg_era5`.
- ETOPO ice (`surface − bed` if > 50 m) is not Lunar Prospector hydrogen.
- A new search overwrites `shortlist.json` and **does not delete** `filtered.json`.
- There is no heatmap layer usable from the UI (controls are commented out).

## How to check

There is no CI (`.github/workflows` does not exist). The frontend has no tests.

```bash
# From backend/. Lunar only: pyproject.toml sets testpaths = ["tests/lunar"].
cd backend
.venv/bin/python -m pytest
```

Covers the `lunar_data` package. Tests marked `local_data` do `pytest.skip` if the NASA IMG files are missing.

```bash
# Earth search, API, worker, activities, history, notify.
cd backend
.venv/bin/python -m pytest tests/earth
```

```bash
# MODIS / ERA5 / SoilGrids readers. Needs pyhdf and rasterio.
# From the repo root; the Makefile venv is backend/.venv.
PYTHONPATH=backend/processing backend/.venv/bin/python -m pytest backend/tests/earth_data
```

The repo README documents the same suite in PowerShell against the root `.venv`, not against `backend/.venv`.

```bash
cd mcp
npm test
```

Runs `applyFilters`, MCP contract, `buscar`, activities, and `reply`. `mcp/test/server.test.mjs` **writes** `data/earth/filtered.json` and restores it at the end (`backupFiltered` / `restoreFiltered`). Do not run it on top of a `filtered.json` you care about without knowing there is a backup; a mid-suite kill can leave the test file in place.

## Where to go next

| Doc | Covers |
|-----|--------|
| [README.md](README.md) | Lunar package `lunar_data`, example JSON, `earth_data` readers. Does not replace this guide's startup. |
| [docs/01-problema-criterios.md](docs/01-problema-criterios.md) | Shortlist filter criteria and the hackathon problem. |
| [docs/moon/README.md](docs/moon/README.md) | LOLA/Diviner/hydrogen extraction, lunar env vars, MVP on another machine. |
| [docs/moon/activity-presets.md](docs/moon/activity-presets.md) | What a preset is: `weights` are not a paper; `search` is not a lunar measurement. |
| [mcp/README.md](mcp/README.md) | MCP registration, tools, troubleshooting. |

Doc ↔ code drifts the reader will hit:

1. **Old scripts.** `docs/01-problema-criterios.md` cites `scripts/serve_search.py`, `scripts/search_earth.py`, and `scripts/similarity.py`. Today: `uvicorn app.main:app`, `backend/app/cli/search_earth.py`, `backend/app/services/earth/similarity.py`.
2. **Token.** `mcp/README.md` says `/tmp/artemis-notify.token` and `serve_search`. The real path is `output/artemis-notify.token` relative to the repo root (`backend/rts.toml`).
3. **Venv.** Makefile → `backend/.venv`. MCP worker → `.venv` at the root. `docs/moon/README.md` also installs the venv at the root, plus geospatial and earth-extras locks.
4. **PowerShell.** Root README and `docs/moon/README.md` document Windows startup (`py -3.12`, `npm.cmd`). On Linux use the commands in this guide.
5. **CLI names.** `mcp/README.md` talks about `extract_earth_columns.py`; the real command is `python -m app.cli.extract_earth_columns` from `backend/`.
