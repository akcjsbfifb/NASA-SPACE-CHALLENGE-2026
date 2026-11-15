# Integración del módulo lunar con el equipo terrestre

## Ubicación e interfaces

Paquete único `lunar_data` en `backend/processing/lunar_data/`. La ruta antigua
era `NASA-Lunar-Studies/src/lunar_data/`. Conservar imports públicos y retirar
el `sys.path` físico antiguo que aún aparece en la rama de comparación.

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-lunar.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .\backend
```

`LolaRaster`, `sample()`, `sample_slope()`, `load_metadata`, `MetadataError`,
`python -m lunar_data` y `backend/scripts/extract_moon.py` siguen disponibles. La clase
nueva es `lunar_data.lunar_prospector.LunarProspectorHydrogen`. Los originales
permanecen locales e ignorados. No se cambian frontend, endpoints ni buscador.

Nota histórica única: se retiró completamente LEND del proyecto activo; el
commit `b79f1b4` permite recuperar su código. Sus originales locales no se borraron.
El registro pasa a 2.0.0 por esta sustitución deliberada; no hay alias, lector,
dependencia de datos ni exportación del procesador retirado.

## Lo que necesita Nico

Para consumir resultados basta el JSON y/o CSV consolidado de `data/moon/`:
no hacen falta originales NASA, Rasterio ni instalar el paquete científico.
Un adaptador Python puede usar `json` y `csv` de la biblioteca estándar. Para
regenerar mediciones se necesitan el paquete, los originales indicados en la
guía y dependencias geoespaciales sólo para Diviner. `pvl` sigue siendo necesario
para interpretar las etiquetas LOLA; no es una dependencia exclusiva retirada.

El JSON mantiene `sites[].id` y las coordenadas solicitadas/normalizadas. El CSV
full contiene siete valores y sus estados, 33 columnas; el perfil core conserva
17 columnas. No hay tabla auxiliar por sensores/períodos. Vincular por `site_id`
y SHA-256, no por orden de filas. Las coordenadas son planetocéntricas, este
positivo; se conserva −10° en el CSV y la normalización está en el JSON.

El catálogo del compañero usa `id`, `lat`, `lng`: mapear a `site_id`,
`latitude_deg`, `longitude_deg` y confirmar marco. Los dos sitios `*_test_only`
siguen siendo ejemplos. Los seis alunizajes Apolo salen de
`frontend/src/data/lunarLandings.ts`, llevan `is_example: false` y `source`, y
se sirven por `GET /moon?site=apollo-11` sin originales NASA ni stack
geoespacial. Ese `source` aclara que las coordenadas no se verificaron todavía
contra un catálogo primario.

## Compatibilidad científica antes de asignar pesos

| Variable lunar | Magnitud terrestre existente | Decisión |
|---|---|---|
| Pendiente en grados | Gradiente ETOPO en grados | Definición semejante; revisar escala, dx mínimo terrestre de 200 m, bordes y faltantes. No habilitar automáticamente. |
| Rugosidad LDRM en m | RMS de diferencias de alturas 3×3 | Distintas definiciones y soportes. Normalización exploratoria pendiente de distribuciones representativas, máscara y parámetros versionados. |
| Elevación sobre esfera | Elevación ETOPO | No comparar alturas absolutas sin criterio de referencia vertical. |
| TBOL/TREG nocturnas en K | WorldClim mínimo mensual de aire | No equivalentes por convertir K a °C. |
| Fracción rocosa | Clase litológica GLiM | No equivalentes. |
| Hidrógeno estimado en ppm | Espesor de hielo ETOPO superficie menos lecho | No equivalentes; tampoco existe aquí humedad o concentración terrestre de H validada. Mostrar contextual, sin peso automático. |

No hay fórmula ni calibración nueva. La regla de review
`rough_scale=max(0.25,abs(roughness)*(50/30))` no es evidencia de equivalencia
física. El shortlist filtrado no representa una distribución global apta para
calibrar. Datos faltantes nunca se sustituyen por ceros para completar el puntaje.

## Estado del buscador y orden de integración

La referencia auditada de `main` es `ee5bde2`, ya incorporada por merge normal
en `f2c16e5`; sus siete cambios eran frontend, sin cambios de backend. Review
terrestre observada: `b84c253`, con columnas memmap. No se modificó ni integró.

El buscador no importa CSV lunares: recibe `/search`, con los nombres de
variable que declara `data/earth/analogs.json` (y el alias `tmin` por
compatibilidad). `/moon?site=<id>` lee el JSON publicado y devuelve las siete
magnitudes con `available`, `status` y `reason`; una coordenada suelta sigue
sampleando los rásters LOLA. El promedio sólo puede incluir variables que el
contrato habilite: hoy la búsqueda desde la Luna manda únicamente rugosidad, y
rugosidad está marcada como proxy (tier B), no como comparable.

Este checkout no tiene Parquet terrestre ni `data/earth/columns/`. Su ejecución
requiere los datos y el manifiesto generados por `extract_earth_columns.py` en
review, o PyArrow para la versión de main. El entorno lunar no instala el stack
web/terrestre. No se afirmó una prueba HTTP o frontend extremo a extremo.

El frontend llama 127.0.0.1:8787 para `/search`, `/cell` y `/scene`.
`backend/scripts/serve_search.py` ocupa ese puerto; el Makefile FastAPI propone el mismo, pero
su router sólo registra health/network. Coordinar un responsable del puerto y
el servicio correcto; este módulo offline no necesita ninguno.

Orden recomendado: revisar la rama lunar e integrarla en main cuando se apruebe;
luego el responsable de review incorpora main y actualiza el adaptador/imports.
Finalmente acordar normalización y pesos. La disponibilidad de siete variables
no significa que las siete sean científicamente comparables ni usadas en similitud.
