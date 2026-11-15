# NASA Space Apps Challenge 2026

Repositorio compartido del equipo. Artemis integra una interfaz web, una API
de búsqueda de análogos terrestres y el paquete lunar `backend/processing/lunar_data/`.
El servidor MCP es opcional. Los resultados son exploratorios y no evalúan
la seguridad de aterrizaje.

## Requisitos previos

- Python **3.12** y `pip`; el entorno lunar se verificó con Python 3.12.10.
- Node.js **22.12 o posterior** y npm. Vite también admite Node 20.19 o posterior;
  usar una versión soportada indicada en la [guía de Vite](https://vite.dev/guide/).
- Git, conexión para instalar paquetes y espacio para los datos opcionales. El
  índice terrestre del equipo ocupa varios GB; los TIFF globales Diviner ocupan
  aproximadamente 3,3 GB cada uno.
- El índice terrestre compatible debe obtenerse del equipo: **no está en Git**.
  Apollo puede consultarse desde el JSON versionado sin los IMG originales.

Clonar y entrar al proyecto:

```bash
git clone https://github.com/akcjsbfifb/NASA-SPACE-CHALLENGE-2026.git
cd NASA-SPACE-CHALLENGE-2026
```

Repositorio compartido del equipo. Este README cubre el paquete lunar
`backend/processing/lunar_data/` y los lectores terrestres de
`backend/processing/earth_data/`. El arranque de API, UI y MCP en Linux
está más abajo; las instrucciones de Windows / PowerShell se conservan.

## MoonStudies — módulo de datos lunares

Extractor local de **elevación LOLA LDEM 16**, **rugosidad LOLA LDRM 32/50**
y **pendiente derivada del LDEM por diferencias centrales**
para coordenadas lunares. Exporta JSON con unidades, celdas consultadas,
procedencia, hashes y calidad de procesamiento. No calcula similitud terrestre
ni evalúa seguridad de aterrizaje.

El código está en `backend/processing/lunar_data/`. La ruta local predeterminada
de datos originales es `data/raw/`, ignorada por Git. Los JSON pequeños de
`data/moon/` pueden consumirse sin abrir los rásteres. El CLI lunar funciona sin
red salvo que se configuren expresamente fuentes adicionales remotas.

## Instalación del backend

Desde la raíz de este repositorio, con Python 3.12:

```powershell
# Crear el entorno solamente si no existe .venv:
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-lunar-geospatial.lock.txt
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-earth-extras.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .\backend
```

No es necesario activar el entorno ni cambiar la política de ejecución: se usa
el ejecutable directamente. `requirements.txt` instala la API y dependencias
generales; el archivo geoespacial incluye el entorno lunar fijado y Rasterio;
`requirements-earth-extras.txt` instala `pyhdf` para HDF4 de MODIS. No hace falta
instalar React, NumPy, GDAL o HDF4 individualmente cuando existen ruedas
compatibles. Si una plataforma no tiene ruedas compatibles, consultar la
[instalación de Rasterio](https://rasterio.readthedocs.io/en/stable/installation.html)
y [pyhdf](https://pypi.org/project/pyhdf/0.11.7/) para sus requisitos nativos;
no se validaron todas las arquitecturas. La web puede abrir los Apollo sin MODIS,
pero el enriquecimiento completo necesita los extras geoespaciales.

En Linux/macOS, desde la raíz, con `python3.12` disponible:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python -m pip install -r backend/requirements-lunar-geospatial.lock.txt
.venv/bin/python -m pip install -r backend/requirements-earth-extras.txt
.venv/bin/python -m pip install --no-deps -e backend
```

Si se prefiere activar el entorno, usar `.\.venv\Scripts\Activate.ps1` en
PowerShell o `source .venv/bin/activate` en Linux/macOS. La activación de
PowerShell depende de la política local; los comandos anteriores la evitan.

## Frontend y ejecución local

El frontend administra React, TypeScript, `react-globe.gl`, Three.js y las
demás dependencias mediante `frontend/package-lock.json`. Desde la raíz del
checkout recién clonado:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

En Linux/macOS usar `npm ci` y `npm run dev`. En otra terminal, desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8787
```

En Linux/macOS: `.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8787`.
Abrir `http://127.0.0.1:5173/`; Vite reenvía `/api` al backend en el puerto
8787. Las dos terminales deben permanecer abiertas. La API inicia sin cargar el
índice, pero una búsqueda terrestre necesita las columnas descritas abajo.

Comprobación rápida en PowerShell, con la API iniciada:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8787/moon?site=apollo-11'
Invoke-RestMethod 'http://127.0.0.1:8787/activities'
# Requiere el índice terrestre instalado:
Invoke-RestMethod 'http://127.0.0.1:8787/search?slope=1&roughness=0.35&candidate_limit=50'
```

En Linux/macOS se pueden consultar las mismas URL con `curl`. Apollo debe devolver
`measurements`; la búsqueda puede tardar al cargar el índice. Si faltan archivos
o falla una fuente, revisar `available`, `status` y `reason`: un dato ausente
no es cero. El mapa base y algunas imágenes o fuentes adicionales requieren red.

## Datos científicos y configuración

### Índice terrestre ya construido

Pedir al equipo una copia del índice compatible y su `columns.json` de procedencia.
No se distribuye en este repositorio ni se descarga automáticamente de GitHub.
La ubicación predeterminada es `data/earth/columns/`; debe contener:

```text
manifest.json                  lat.f32                    lon.f32
elevation_m.f32                slope_deg.f32              roughness_m.f32
tmin_coldest_month_c.f32       ice_thickness_m.f32        lithology_code.u8
```

`data/earth/columns.json` y `data/earth/analogs.json` están versionados; si las
columnas proceden de otro lugar, compartir también el `columns.json` compatible
en el directorio padre de `columns/`. Para usar una ruta externa, antes de
iniciar la API configurar `GURVICH_COLUMNS_DIR` con la carpeta que contiene
`manifest.json`, no con el archivo:

```powershell
$env:GURVICH_COLUMNS_DIR = 'C:\ruta\al\indice\columns'
```

En Linux/macOS: `export GURVICH_COLUMNS_DIR='/ruta/al/indice/columns'`. Sustituir
la ruta de ejemplo. El manifiesto registra tipos y cantidad de filas; el equipo
debe comprobar que las columnas y los metadatos corresponden al mismo índice.
Sin él, `/search` falla, aunque `/moon?site=apollo-11` sigue disponible.
La configuración general de rutas y puertos está en `backend/rts.toml`;
opcionalmente, `RTS_LOCATION` puede apuntar a otro archivo TOML compatible.

### LOLA y Lunar Prospector para coordenadas libres

Los seis Apollo se leen de `data/moon/apollo_measurements.json`, incluido en Git.
Para muestrear coordenadas libres, descargar los tres archivos de cada producto
del [directorio LOLA de NASA PDS](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/):

```text
data/raw/lola/ldem/ldem_16_float.img
data/raw/lola/ldem/ldem_16_float.xml
data/raw/lola/ldem/ldem_16_float.lbl
data/raw/lola/ldrm/ldrm_32_50_float.img
data/raw/lola/ldrm/ldrm_32_50_float.xml
data/raw/lola/ldrm/ldrm_32_50_float.lbl
```

También se admite la extensión `.lbl.txt` para las etiquetas. LDEM aporta
elevación y pendiente derivada; LDRM aporta rugosidad. Sin los dos productos
LOLA la extracción de coordenadas libres no se inicia. Para el hidrógeno libre,
obtener `hydrogenhd.dat` y `hydrogenhd.txt` del [producto especial Lunar
Prospector de NASA PDS](https://pds-geosciences.wustl.edu/missions/lunarp/reduced_special.html)
y colocarlos juntos en `data/raw/lunar_prospector/hydrogen/`. El TXT es la
referencia ASCII utilizada por el lector; sin ambos archivos el hidrógeno queda
no disponible, pero las demás mediciones pueden continuar.

Si están fuera del repositorio, configurar antes de iniciar la API:

```powershell
$env:LUNAR_DATA_ROOT = 'C:\ruta\a\lola' # contiene ldem/, ldrm/ y diviner/
$env:LUNAR_HYDROGEN_ROOT = 'C:\ruta\a\hydrogen' # contiene DAT y TXT
```

En Linux/macOS usar `export LUNAR_DATA_ROOT='/ruta/a/lola'` y
`export LUNAR_HYDROGEN_ROOT='/ruta/a/hydrogen'`. Estas variables corresponden a
la API; para el CLI lunar usar `--data-root` y, si se requieren fuentes
adicionales, una configuración `--sources` como las de `data/moon/`.

### Diviner para coordenadas libres

Los productos RA, TBOL y TREG proceden de los [GHRM de NASA PDS](https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_ghrm/geotiff/).
Dentro de la carpeta LOLA colocar cada XML en la ruta indicada; el TIFF del
mismo nombre es opcional si se opta por acceso remoto:

```text
data/raw/lola/diviner/rock_abundance/dghrm_ra_sam_70s70n_tif.xml
data/raw/lola/diviner/bolometric_temperature/dghrm_tbol_sam_70s70n_tif.xml
data/raw/lola/diviner/regolith_temperature/dghrm_treg_sam_70s70n_tif.xml
```

Para uso local, colocar junto a cada XML su archivo `.tif` correspondiente.
Alternativamente, con los XML y Rasterio instalados, habilitar antes de iniciar
la API `$env:LUNAR_DIVINER_REMOTE = '1'` en PowerShell o
`export LUNAR_DIVINER_REMOTE=1` en Linux/macOS. El lector intenta acceder por
rangos HTTP con un presupuesto compartido; depende del servicio y la red, y no
garantiza que toda consulta termine dentro de un plazo fijo. Si no se configura
una fuente, falla la red o el punto está fuera de **70° S–70° N**, esas variables
quedan no disponibles; no se sustituyen por cero. Los Apollo publicados no
necesitan volver a descargar estos TIFF para mostrar sus valores.

### MODIS, ERA5-Land y SoilGrids

- **MODIS:** obtener el archivo de enero de 2025
  `MOD11C3.A2025001.061.2025035172114.hdf` desde la [página oficial MOD11C3](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/MOD11C3/)
  y colocarlo en `data/raw/earth/modis/`. LAADS/Earthdata puede requerir una
  cuenta gratuita de [NASA Earthdata Login](https://urs.earthdata.nasa.gov/) y
  autorización o token para descargar; no guardar credenciales en el repo.
  El backend usa el HDF local; si falta o falla `pyhdf`, MODIS queda ausente y
  la búsqueda continúa con los demás datos válidos. Es un mes de ejemplo, no
  una climatología anual.
- **ERA5-Land:** el adaptador consulta la [API histórica Open-Meteo](https://open-meteo.com/en/docs/historical-weather-api)
  para los candidatos, sin descargar manualmente un dataset global. Requiere
  conexión cuando falta la caché; guarda respuestas bajo `data/raw/earth/era5_land/`.
- **SoilGrids:** se consultan recortes WCS de [fragmentos gruesos 0–5 cm](https://maps.isric.org/generated/soilgrids/cfvo.html),
  sin descargar el mapa completo. Requiere red cuando el recorte no está en
  `data/raw/earth/soilgrids/`; ver la [documentación WCS](https://docs.isric.org/globaldata/soilgrids/wcs.html).
  Es contexto, no un puntaje equivalente a la abundancia de rocas lunar.

Comprobar que Python reconoce `pyhdf` y que el lector puede abrir el archivo
local, desde la raíz y sin consultar servicios remotos:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend/processing'); from earth_data.modis import ModisMonthly; p=ModisMonthly('data/raw/earth/modis/MOD11C3.A2025001.061.2025035172114.hdf'); p.__enter__(); print(p.sample(-85, 0)); p.__exit__(None,None,None)"
```

En Linux/macOS usar el mismo comando reemplazando el ejecutable por
`.venv/bin/python`. Un resultado ausente puede reflejar NoData o calidad del
píxel, aunque el archivo se abra correctamente.

### Reconstruir el índice terrestre — alternativa avanzada

Para **usar** el índice compartido no hacen falta los originales ETOPO, WorldClim
o GLiM. Reconstruirlo es una tarea independiente, lenta y de gran espacio, no
un paso normal de instalación. El constructor espera en `data/raw/`:

- `ETOPO_2022_v1_60s_surface.tif` y `ETOPO_2022_v1_60s_bed.tif`, de [NOAA ETOPO 2022](https://www.ncei.noaa.gov/products/etopo-global-relief-model).
- Los 12 `worldclim/wc2.1_10m_tmin_*.tif` de [WorldClim 2.1](https://worldclim.org/data/worldclim21.html).
- `glim/glim_wgs84_0point5deg.txt.asc`, del [GLiM 0,5° publicado en PANGAEA](https://doi.pangaea.de/10.1594/PANGAEA.788537), preparado con el nombre y la grilla esperados por el constructor.

El espesor de hielo se deriva de los dos rásteres ETOPO; no requiere un cuarto
dataset separado. Los módulos `app.cli` se ejecutan desde `backend/`: el constructor no define
una opción de ayuda y comienza a procesar al ejecutarse. Para reconstruir de
verdad, usar desde `backend/` `..\.venv\Scripts\python.exe -m app.cli.build_earth`
y después `..\.venv\Scripts\python.exe -m app.cli.extract_earth_columns`.
En Linux/macOS sustituir el ejecutable por `../.venv/bin/python`. Estos procesos
escriben el parquet y las columnas predeterminadas; la extracción **sobrescribe**
archivos en su destino. Preparar un destino separado con `--out` y conservar los
datos previos; no ejecutar estos comandos sobre un índice que se quiera preservar.

## MCP opcional

El MCP no es necesario para ejecutar la web. Desde `mcp/`, instalar sus propias
dependencias con `npm.cmd ci` en Windows o `npm ci` en Linux/macOS; el servidor
usa transporte stdio y se inicia con `npm.cmd start` o `npm start`. En un cliente
MCP, registrar el comando `node` con el argumento `mcp/index.mjs` y el directorio
de trabajo en la raíz del checkout; consultar [mcp/README.md](mcp/README.md) para
ejemplos específicos del cliente. No incluir tokens en la configuración compartida.

El worker MCP espera por defecto el entorno `.venv` en la raíz: usa
`.venv/Scripts/python.exe` en Windows y `.venv/bin/python` en Linux/macOS. Al
crear el servidor mediante `createServer({ python: ... })` se puede indicar otro
ejecutable explícitamente; esa opción tiene prioridad. La web no depende del
worker. Si el índice está fuera de `data/earth/columns/`, configurar también
`ARTEMIS_COLUMNS_DIR` con la carpeta de columnas para el fallback del worker;
`GURVICH_COLUMNS_DIR` configura la API. El MCP dispone de criterios terrestres
propios y no sustituye la etapa térmica lunar de la web.

## Datos fuera de Git y problemas frecuentes

`data/raw/`, `NASA-Lunar-Studies/`, `data/earth/columns/`, `.venv/`, cachés y
`output/` están ignorados. No subir HDF, IMG, TIFF, índices, cachés ni credenciales;
revisar `git status` antes de compartir cambios locales.

- **API sin columnas:** copiar el índice y verificar `GURVICH_COLUMNS_DIR`,
  `manifest.json`, los nombres y tamaños de las columnas.
- **Apollo funciona, coordenada libre no:** revisar las rutas LOLA y las tres
  piezas IMG/XML/LBL de ambos productos; revisar también el hidrógeno y los
  XML Diviner si se necesitan esas variables.
- **Temperaturas o suelo ausentes:** verificar HDF, extras Python, conectividad,
  cobertura y estado de la fuente. Las APIs externas pueden fallar; la caché
  no garantiza cobertura completa.
- **Errores al instalar dependencias nativas:** confirmar versión y arquitectura
  de Python y disponibilidad de ruedas; consultar las guías de Rasterio y pyhdf.
- **Navegador sin API:** comprobar ambos procesos y los puertos 5173 y 8787.

## Cómo levantarlo (Linux)

Prerrequisitos: Python 3.12 y Node. La API queda en `127.0.0.1:8787` y la UI en
`127.0.0.1:5173`. MCP habla por stdio; no abre puerto. Esos `cd` son relativos
a la raíz del repositorio, no a un home.

**1. Columnas terrestres (una vez) y API.** `land_60s.parquet` y
`data/earth/columns/` pueden no estar en Git. Desde el directorio `backend`:
`make venv`, extraer columnas y levantar la API.

```bash
cd backend
make venv
.venv/bin/python -m app.cli.extract_earth_columns
make dev
```

`make dev` sirve uvicorn en `127.0.0.1:8787`.

**2. UI**

```bash
cd frontend
npm install
npm run dev
```

Vite escucha `127.0.0.1:5173` y proxifica `/api` hacia `http://127.0.0.1:8787`.

**3. MCP**

```bash
cd mcp
npm install
npm start
```

`npm start` ejecuta `node index.mjs` por stdio.

Hay dos venv. El Makefile crea `backend/.venv`. `mcp/artemisWorker.mjs` ejecuta
`<repo>/.venv/bin/python` (venv en la raíz del repo). Si solo
existe el del Makefile, `buscar` local no arranca. Con la API en 8787 el worker
reenvía a `GET /search`.

## JSON listo para compartir

El equipo puede usar directamente
[`lola_measurements.example.json`](data/moon/lola_measurements.example.json)
sin descargar los IMG ni instalar Python. Incluye elevación y rugosidad reales
extraídas de LOLA, más pendiente derivada con cinco alturas, para los dos puntos de prueba de
`backend/tests/lunar/fixtures/sites.example.json`.
Ambos están marcados `is_example: true`; no son sitios de misión definitivos.

La [guía de consumo y reproducción](docs/moon/README.md)
explica el formato y cómo regenerarlo. Las variables todavía no procesadas
mantienen valores nulos y estados explícitos. El JSON no calcula similitud.

El método y sus límites están en la
[metodología LOLA](docs/moon/lola_methodology.md#pendiente-derivada-de-ldem).

Para compartir una tabla ancha también está disponible
[`lola_measurements.example.csv`](data/moon/lola_measurements.example.csv).
Se genera desde el JSON completo, sin abrir datos NASA ni recalcular valores:

```powershell
.\.venv\Scripts\python.exe -m lunar_data.csv_export --input .\data\moon\lola_measurements.example.json --output .\output\moon_examples.csv
```

Elegir una salida nueva. El [formato CSV](docs/moon/README.md#csv-ancho-desde-el-json)
conserva estados, coordenadas originales y SHA-256 del JSON fuente.

El [CSV consolidado de siete variables](data/moon/lunar_measurements.example.csv)
agrega RA, TBOL, TREG y `hydrogen_abundance_ppm` (Lunar Prospector, ppm por peso).
Para generarlo usar `--profile full` (33 columnas). El hidrógeno es una
estimación contextual, no agua/hielo confirmado ni una entrada automática al
puntaje terrestre. Los formatos `core` y `full` se obtienen del mismo JSON.

## Datos requeridos para regenerar las mediciones

Usá los archivos LOLA descritos en [Datos científicos y configuración](#lola-y-lunar-prospector-para-coordenadas-libres).
Se interpretan las referencias de los XML sin modificar archivos. Se admiten
esos dos productos globales float, con su geometría y marco DE421. El CLI no
descarga datos automáticamente salvo que se configure una fuente remota.

## Extracción real con coordenadas de ejemplo

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m lunar_data `
  --latitude 0 --longitude 0 --example `
  --site-id equatorial_test_only `
  --output .\output\lola_example.json
```

Las coordenadas son un **ejemplo de prueba**, no un sitio de misión seleccionado.
La muestra local verificada devuelve aproximadamente −718,685 m de elevación y
0,429611 m de rugosidad. El punto cae en un borde: se consulta la celda al sur y
al este, con centros distintos para cada resolución. El JSON conserva los
valores float32 decodificados, sin atribuirles esa cantidad de dígitos de exactitud.

La salida se crea solamente si no existe: para repetir el comando, elegí otro
nombre. Nunca se sobrescriben entradas ni resultados existentes.

Para procesar la lista de ejemplos incluida:

```powershell
.\.venv\Scripts\python.exe .\backend\scripts\extract_moon.py `
  --sites .\backend\tests\lunar\fixtures\sites.example.json `
  --output .\output\lola_sites_example.json
```

Para sitios del equipo, copiá el archivo de ejemplos y registrá `id`,
`latitude_deg`, `longitude_deg` e `is_example` explícitamente. Las longitudes son
este positivo; se aceptan negativas y se normalizan a [0, 360). El marco de
entrada debe ser Mean Earth/Polar Axis de DE421; no se transforman otros marcos.

`--data-root` permite indicar otra carpeta LOLA y `--registry` otro registro de
variables compatible. Las rutas por defecto apuntan a las entradas locales
originales y a `data/moon/variables.json` del checkout editable. Las rutas que
se pasan explícitamente siguen siendo relativas al directorio actual.
`--help` muestra todas las opciones.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests\lunar
```

Las pruebas sintéticas no necesitan descargar archivos. Las pruebas marcadas
`local_data` usan los IMG locales si están disponibles; en otro equipo se omiten
si esos datos no existen. Se comparan píxeles con `seek` + `struct.unpack`, además
de probar metadatos incompatibles, conversiones, bordes, faltantes y JSON.

Con pvl 1.3.2 aparece un `PendingDeprecationWarning` al importar su clase interna
`Units`; la suite no lo silencia. No indica una conversión errónea de estos datos.

## Documentación científica y contrato de salida

- [Registro de variables incluidas, pendientes y excluidas](docs/moon/variables.md).
- [Metodología LOLA, contrato JSON y límites de validación](docs/moon/lola_methodology.md).
- [Registro estructurado de variables](data/moon/variables.json).
- [Migración y coordinación con la rama de comparación lunar](docs/moon/integration.md).

El registro general contiene definiciones y estados. El JSON por sitio contiene
mediciones y disponibilidad. `used_in_similarity: null` significa que este
módulo no conoce la decisión del comparador externo, incluso si un valor está
disponible. Las variables pendientes no tienen valores inventados.

Ningún resultado de este módulo permite declarar un sitio seguro para aterrizar.

## Lectores terrestres

Estos lectores enriquecen una lista ya seleccionada. Las entradas originales y cachés deben quedar
en `data/raw/earth/`, ignorado por Git. Se necesitan NumPy, Rasterio y
`pyhdf==0.11.7` (`backend/requirements-earth-extras.txt`). Desde la raíz:

```powershell
$env:PYTHONPATH = (Resolve-Path .\backend\processing).Path
.\.venv\Scripts\python.exe -m pytest .\backend\tests\earth_data
```

`ModisMonthly(path)` abre una vez el HDF4 MOD11C3.061 y `sample_many()`
consulta sólo los píxeles indicados. Verifica DOI, grilla, capas, constantes y
atributos. Devuelve LST nocturna mensual en K, valor almacenado, QC, máscara de
noches despejadas y hora media de observación UTC. La política provisional
acepta QA obligatorio `00`, bit de calidad de datos `0` y una o más noches
despejadas. Datos que no la cumplen quedan como ausentes; no son cero. El
archivo enero de 2025 no es una climatología.

`open_meteo.sample_many(points, start, end, cache_dir)` pide ERA5-Land de
0–7 cm por lotes de hasta 20 ubicaciones. La selección temporal es la media de
las horas disponibles dentro de 30 minutos de medianoche solar media local,
calculada como UTC + longitud/15. Guarda la serie horaria, la unidad original
°C, valor convertido K, coordenada solicitada y celda del proveedor. Cerca de los
polos, medianoche solar no garantiza oscuridad. No equipara suelo terrestre a
temperatura radiométrica del regolito lunar. La caché registra período, unidad,
modelo y adquisición, y no guarda errores de red.

`soilgrids.inspect_service()` consulta GetCapabilities y DescribeCoverage.
`soilgrids.sample_many(points, cache_dir)` usa cobertura `cfvo_0-5cm_mean`,
reproyecta desde WGS84 a Homolosine y agrupa candidatos en recortes alineados de
1 km. Conserva GeoTIFF mínimo y SHA-256. En la inspección real, WCS declaró
ejes proyectados x/y, resolución 250 m y no declaró nil values. Como el servicio
devolvió cero tanto en océano sin máscara como en otros puntos, todo cero sin
NoData declarado se marca ambiguo y no se presenta como medición válida.
Esto puede excluir ceros reales. El valor almacenado en cm³/dm³ se divide por
10 para porcentaje volumétrico y por 1000 para fracción volumétrica. Es una
propiedad del suelo, no fracción de superficie rocosa Diviner.

`enrich.enrich_candidates()` admite hasta 200 candidatos preseleccionados y
adjunta las tres fuentes sin cambiar ni recalcular sus puntuaciones. La salida
declara que es enriquecimiento posterior, no búsqueda global multivariable.
La API `POST /enrich` acepta hasta 50 coordenadas y usa enero de 2025 como
periodo reproducible de prueba; evita consultas concurrentes y responde sin
incluir la serie horaria completa, que queda en la caché. La interfaz solicita
enriquecimiento para los primeros 50 resultados después de mostrar el ranking;
los demás aparecen como no procesados. El panel seleccionado puede solicitar
su propia coordenada. El endpoint `/enrich` conserva las puntuaciones recibidas.

### Comparación térmica exploratoria

La rugosidad conserva la función existente `exp(-abs(R_tierra-R_luna)/s)`,
con `s = max(0.25 m, 1.6666666666666667 * abs(R_luna))`, según
`data/earth/analogs.json`. Produce un índice entre 0 y 1; los valores originales
siguen en metros y la ausencia no recibe puntaje. LOLA LDRM y la rugosidad de
ETOPO tienen definiciones y escalas diferentes: el índice no las equipara.

Cuando se elige TBOL/MODIS o TREG/ERA5, `/search` calcula para cada pareja
válida `min(T_lunar_K, T_terrestre_K) / max(T_lunar_K, T_terrestre_K)`.
El cociente de temperaturas absolutas está entre 0 y 1 y equivale a uno menos
la diferencia absoluta dividida por la mayor temperatura. No tiene parámetro
de escala ajustable: por ejemplo, con referencia 100 K, valores de 100, 200,
300 y 400 K producen 1, 0,5, 0,333 y 0,25. Es un índice relativo exploratorio,
no una calibración ni equivalencia física entre productos, profundidades,
horarios o períodos. Los valores originales, control de calidad y enero de 2025
se conservan. No representa una climatología anual.

La búsqueda calcula primero el ranking existente por pendiente y/o rugosidad,
extrae un máximo de 50 candidatos y sólo entonces incorpora temperaturas y
reordena mediante el promedio de puntuaciones disponibles ponderado por los
pesos elegidos. La cobertura mínima se puede elegir sin penalización oculta.
El resultado no es un óptimo global multivariable: el filtro geométrico puede
excluir otras regiones. Una búsqueda sólo térmica aún no genera candidatos y
responde con un error explícito. Datos ausentes no se convierten en cero.

Diviner RA mide fracción superficial de rocas y SoilGrids cfvo fracción
volumétrica de fragmentos: no hay una conversión validada entre ambas. Se
mantienen como contexto sin porcentaje hasta aprobar y validar un proxy.

Ejemplo desde PowerShell con el backend iniciado y el índice externo configurado:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8787/search?slope=1&roughness=0.35&w_slope=0.5&w_roughness=1&tbol_modis=102&w_tbol_modis=0.7&min_coverage=3'
```

`min_coverage=3` exige las tres puntuaciones; el valor predeterminado es 1.
Para ERA5 se usan `treg_era5` y `w_treg_era5`. Los pesos válidos son 0 a 1;
un peso cero excluye la variable. La media usa la suma real de los pesos
de las mediciones disponibles. Esta corrección también afecta búsquedas
geométricas con pesos cuya suma sea menor que uno; coordinarla con Nico.

### Revisión de pendiente

`backend/app/cli/build_earth.py` deriva `slope_deg` de ETOPO 2022 superficie
60 segundos de arco mediante diferencias centrales y distancia longitudinal
proporcional a coseno de latitud. El paso se limita a 200 m, sustituye vecinos
ausentes por el centro y repite bordes. Con el índice externo se reconstruyeron
tres vecindades interiores de alturas; los resultados coincidieron exactamente
con las pendientes almacenadas. No se dispone aquí del ETOPO original para
verificar costas u observaciones independientes.

En la celda (-86.4083328247, 133.7916717529), paso real según la fórmula
esférica ≈116.228 m y paso limitado 200 m: con las mismas cinco alturas se
obtienen 0.165797° y 0.285292°, respectivamente. El límite reduce ese ejemplo
≈0.119495° (≈41.9 % respecto al cálculo sin límite); comienza a actuar sobre
|latitud| ≈83.812°. No se corrigió el método de Nico. Modificarlo exigiría
aprobar la política polar y regenerar el índice y sus puntuaciones afectadas.
La pendiente lunar usa radio 1.737.400 m, separación angular LDEM 1/16°,
longitud periódica y requiere cinco valores válidos. Son definiciones
relacionadas con distancias y reglas de bordes distintas.

### Descarga

- `bolometric_temperature`. LST nocturna MODIS/Terra, MOD11C3.061, en K, grilla de 0,05°. Superficie, no aire. https://ladsweb.modaps.eosdis.nasa.gov/archive/allData/61/MOD11C3 — https://doi.org/10.5067/MODIS/MOD11C3.061
- `regolith_temperature`. ERA5-Land, `monthly_averaged_reanalysis`, `soil_temperature_level_1` (0–7 cm), en K. Modelo, no medición térmica directa. https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-monthly-means
- `rock_abundance`. No hay equivalente global a Diviner. SoilGrids 2.0, `cfvo_0-5cm_mean`, fragmentos gruesos en el suelo. https://files.isric.org/soilgrids/latest/data/cfvo/
- `hydrogen_abundance_ppm`. No hay mapa global en ppm. Lo más cercano es SMAP SPL4SMGP v008, humedad en m³/m³. El espesor de hielo ETOPO no lo reemplaza. https://nsidc.org/data/spl4smgp/versions/8 — https://doi.org/10.5067/T5RUATAQREF8
