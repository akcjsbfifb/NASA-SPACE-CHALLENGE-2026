# Gurvich MCP

Servidor MCP stdio para búsqueda de análogos terrestres, filtrado y lectura de resultados. Comparte archivos con la UI en `data/earth/`.

## Instalación

1. Extraer columnas (una vez por dataset):

   ```bash
   .venv/bin/python backend/scripts/extract_earth_columns.py
   ```

2. Registrar el server MCP.

   El server es MCP por stdio (`node mcp/index.mjs`). Cursor, Claude Code y OpenCode lo lanzan igual. Lo único de Cursor es `.cursor/mcp.json`.

   Cursor — `.cursor/mcp.json`:

   ```json
   {
     "mcpServers": {
       "gurvich": {
         "command": "node",
         "args": ["/home/nicolas/Documentos/NASA-SPACE-CHALLENGE-2026/mcp/index.mjs"],
         "cwd": "/home/nicolas/Documentos/NASA-SPACE-CHALLENGE-2026/mcp"
       }
     }
   }
   ```

   Claude Code: archivo `.mcp.json` en la raíz del repo:

   ```json
   {
     "mcpServers": {
       "gurvich": {
         "type": "stdio",
         "command": "node",
         "args": ["mcp/index.mjs"]
       }
     }
   }
   ```

   OpenCode: archivo `opencode.json`:

   ```json
   {
     "mcp": {
       "gurvich": {
         "type": "local",
         "command": ["node", "mcp/index.mjs"],
         "enabled": true
       }
     }
   }
   ```

   Las tools y el worker de Python son los mismos. El aviso al mapa sigue siendo el browser contra el puerto `8787`, no el IDE. Hacen falta Node, el `.venv` del repo y `data/earth/columns/`.

3. Opcional: tener `backend/scripts/serve_search.py` en `http://127.0.0.1:8787` para que el mapa reciba eventos SSE y el worker evite cargar otra `EarthIndex`.

## Herramientas

| Tool | Escribe | No borra |
|------|---------|----------|
| `buscar` | `data/earth/shortlist.json` | shortlist previa (sobrescribe) |
| `aplicar_filtros` | `data/earth/filtered.json` | `shortlist.json` |
| `limpiar_filtros` | `data/earth/filtered.json` (`filters: []`) | `shortlist.json` |
| `listar` | — | todo |

### `buscar` (misma consulta que la UI)

Parámetros opcionales: `slope`, `roughness`, `tmin`, `ice`, `rock`, `precision` (default `0.7`).

Ejemplo de prompt:

> Busá análogos con slope 8°, roca vb y precision 0.7.

Respuesta al modelo (recortada; el mapa recibe el JSON completo vía SSE):

```json
{
  "target": { "slope_deg": 8 },
  "precision": 0.7,
  "returned": 42,
  "closest": { "closeness": 0.95 },
  "loosest": { "closeness": 0.71 },
  "temperature_mode": "band",
  "variables": ["slope", "rock"],
  "points": [{ "lat": -45.1, "lon": -70.2, "closeness": 0.91 }]
}
```

Como máximo 8 puntos en `points`. Si `serve_search` está activo y responde en `8787`, el worker usa `GET /search` y no reconstruye la grilla en memoria.

### Filtrar

- `aplicar_filtros`: lee shortlist, aplica reglas de catálogo, escribe `filtered.json`. `filters: []` → error `empty_filters`.
- `limpiar_filtros`: pone todos los puntos visibles sin filtros.

### Leer

- `listar`: solo lee `filtered.json`. Si no existe → `no_filter`.

## Anotaciones MCP

- `listar`: `readOnlyHint: true`
- `buscar`, `aplicar_filtros`, `limpiar_filtros`: `destructiveHint: true` (escriben JSON en disco)

## Troubleshooting

| Síntoma | Causa habitual |
|---------|----------------|
| Error al arrancar worker / columnas | Falta `data/earth/columns/`; correr `extract_earth_columns.py`. |
| Primera búsqueda lenta | Sin servidor `8787`: la primera llamada carga la grilla en el proceso worker. |
| `frontend_error` en `buscar` | `serve_search` caído o `POST /notify` rechazado; la búsqueda igual puede devolver puntos. |
| `empty_filters` | Llamaste `aplicar_filtros` con lista vacía. |
| `unknown rock` | Código USGS inválido en `rock`. |

## Seguridad

- Transporte **stdio**: no abre puerto de red para MCP.
- `POST /notify` exige header `X-Gurvich-Notify-Token` (token en `/tmp/gurvich-notify.token`, mode `0600`, regenerado al arrancar `serve_search`).
- `GET /events` (SSE) no usa `Access-Control-Allow-Origin: *`; solo orígenes Vite dev (`localhost` / `127.0.0.1:5173`).
- `buscar` no envía la shortlist entera al modelo: resumen con hasta 8 puntos; el payload completo va al frontend por SSE.