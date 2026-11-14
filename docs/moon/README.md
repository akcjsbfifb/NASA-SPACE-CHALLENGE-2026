# Procesamiento lunar offline

El paquete científico único está en `backend/processing/lunar_data/`. Lee los
productos LOLA LDEM_16_FLOAT y LDRM_32_50_FLOAT locales y genera JSON estricto.
El backend y el frontend pueden consumir el JSON compartido sin abrir mapas.
No se incorporan endpoints, comparadores ni catálogos de localizaciones.

## Instalación desde PowerShell

Desde la raíz del repositorio, con Python 3.12 y un entorno `.venv`:

```powershell
# Sólo si no existe el entorno:
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-lunar.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .\backend
```

Si el entorno ya tiene las dependencias, sólo hace falta reinstalar el paquete
editable mediante el último comando. Esto reemplaza su antigua ubicación; no
se instala otra distribución con otro nombre. El empaquetador usa setuptools;
no se instalan Rasterio/GDAL, PyArrow ni FastAPI para extraer LOLA.

## Entradas locales

Los originales permanecen en `NASA-Lunar-Studies/data/raw/lola/ldem/` y `ldrm/`,
con sus IMG, XML y etiquetas `.lbl` o `.lbl.txt`. Los XML Diviner y los seis
originales LEND también permanecen donde estaban; no los lee esta versión.
No se descargan mapas ni se modifica su contenido.

## Extraer un punto

```powershell
.\.venv\Scripts\python.exe -m lunar_data `
  --latitude 0 --longitude 0 --example `
  --site-id equatorial_test_only `
  --output .\output\moon_point.json
```

La salida debe ser nueva. El ejemplo ecuatorial devuelve aproximadamente
−718,685 m de elevación sobre una esfera de radio 1737400 m y 0,429611 m de
rugosidad. Los decimales completos del JSON permiten reproducir la lectura,
no representan esa exactitud física.

Para los dos puntos de prueba existentes:

```powershell
.\.venv\Scripts\python.exe .\scripts\extract_moon.py `
  --sites .\backend\tests\lunar\fixtures\sites.example.json `
  --output .\output\moon_examples.json
```

El script delega en `lunar_data.__main__.main`; no contiene otro lector.
Los defaults resuelven `NASA-Lunar-Studies/data/raw/lola/` y
`data/moon/variables.json` dentro del checkout editable, independientemente del
directorio de ejecución. `--data-root` y `--registry` permiten rutas explícitas.
Fuera del checkout, por ejemplo con una instalación wheel, deben suministrarse
esas rutas si no están en el directorio de trabajo.

## Identificadores y coordenadas compartidos

`--sites` acepta una lista JSON de objetos con `id`, `latitude_deg`,
`longitude_deg`, `is_example` booleano y un `name` opcional. Los identificadores
se conservan. Las coordenadas son planetocéntricas, este positivo, en el marco
Mean Earth/Polar Axis de DE421. No se transforman otros marcos.

El archivo bajo `tests/lunar/fixtures/` es un fixture, no la fuente de sitios
del proyecto. Los registros reales deben venir del sistema compartido del
equipo; no se copió ni creó un catálogo Apolo. El esquema del catálogo del
compañero requiere un mapeo de campos y revisión de procedencia, no otro
catálogo mantenido por este paquete.

## Mediciones publicables y estados

[`data/moon/lola_measurements.example.json`](../../data/moon/lola_measurements.example.json)
es la publicación mantenida. El
[JSON histórico](../../NASA-Lunar-Studies/examples/lola_measurements.example.json)
permanece byte a byte como referencia de la versión anterior.

Consultar `sites[].measurements.elevation`, `roughness` y `slope`, verificando `available`,
`status`, `unit` y advertencias. Seguir `source_ref` a las fuentes y hashes.
`used_in_similarity: null` indica que el procesador no conoce la decisión del
comparador. Un dato faltante o un procesador pendiente no equivale a cero ni a
condiciones favorables.

El registro 1.2.0 incorpora pendiente derivada del LDEM; el paquete es 0.2.0.
La salida conserva el contrato 1.0.0 con campos aditivos de método, entradas y
distancias. `sources.slope` referencia `elevation`: no es otro producto NASA.
`input_samples` conserva las cinco alturas originales y convertidas, índices,
centros, unidades y estados. Una altura ausente invalida la pendiente completa.
Diviner, iluminación, LEND y normalización quedan para otras etapas.

## CSV ancho desde el JSON

El [CSV de ejemplo](../../data/moon/lola_measurements.example.csv) es una vista
tabular del JSON completo existente, no su reemplazo. Una fila representa un
sitio y conserva el orden de `sites`. El exportador sólo usa biblioteca estándar,
no interpreta etiquetas PDS, importa lectores, calcula mediciones ni abre NASA.

Desde la raíz del repositorio, en PowerShell:

```powershell
.\.venv\Scripts\python.exe -m lunar_data.csv_export `
  --input .\data\moon\lola_measurements.example.json `
  --output .\output\moon_examples.csv
```

La salida debe ser nueva: el comando no sobrescribe CSV existentes ni el JSON.
Para reproducir el archivo canónico, se usa una ruta nueva en `data/moon/`,
por ejemplo `lola_measurements.review.csv`, y se comparan sus bytes con
`lola_measurements.example.csv`. No hace falta descargar NASA para esta conversión.

Formato CSV 1.0: UTF-8 sin BOM, coma, punto decimal, encabezado fijo y saltos LF.
El módulo `csv` de Python escapa comas, comillas y saltos dentro de campos.
No abrir/guardar desde una planilla antes de comparar hashes: puede redondear
números o cambiar el separador. Al importar en una planilla, elegir coma y UTF-8.

| Columnas | Contenido |
|---|---|
| `site_id` | `sites[].id`; único, conservado sin modificar |
| `latitude_deg`, `longitude_deg` | Coordenadas **solicitadas** del JSON: planetocéntricas y este positivo; conserva −10°, no lo sustituye por 350°. El marco completo sigue en `coordinate_reference` del JSON. |
| `elevation_m`, `roughness_m`, `slope_deg` | `measurements.<variable>.value`, sin normalización, conversión de unidades ni redondeo; cero válido se conserva como cero |
| `<variable>_status` | Estado literal del JSON, para `elevation`, `roughness` y `slope` |
| `<variable>_available` | `true`, `false` o celda vacía si el JSON declara `null` (desconocido) |
| `<variable>_reason` | Motivo literal del JSON; vacío si es nulo |
| `source_json_file`, `source_json_sha256` | Nombre del archivo fuente y SHA-256 de sus bytes completos; vincula la fila con su evidencia científica |

Son 17 columnas. Los valores no disponibles se exportan vacíos: no se usan
ceros, cadenas `None` ni `NaN`. Los tres estados auxiliares no se infieren de
un valor vacío: se copian del JSON. `missing` indica ausencia de una medición;
`not_sampled` indica que la política no permite muestrear ese punto;
`not_implemented` indica un procesador pendiente. En los productos pendientes,
fuera de cobertura puede aparecer como `not_implemented`, `available: false`
y `reason: outside_declared_latitude_coverage`; no se pierde esa distinción.
En el ejemplo actual las tres variables están disponibles en ambos sitios.

El SHA se calcula sobre el mismo contenido que se convierte. El nombre es una
referencia de archivo, no una ruta absoluta ni garantía de que esté al lado del
CSV: compartir ambos y verificar el hash. Con ese JSON, `site_id` y la variable
se recuperan fuentes NASA, método, unidades, vecinos, advertencias y calidad.
Ni el CSV ni sus columnas de estado habilitan similitud automáticamente.

La tabla ordenada `VARIABLE_COLUMNS` en `csv_export.py` permite añadir columnas
para LEND, Diviner e iluminación tras aprobar sus identificadores y unidades.
Cada entrada futura agrega su valor y las tres columnas de estado; requerirá
pruebas y actualizar el contrato CSV. No se anticipan unidades ni valores de
procesadores pendientes. Todas las variables actuales continúan en el JSON.

Unidades incorrectas, valores no finitos, sitios duplicados, registros ausentes
o contradicciones entre valor y disponibilidad se rechazan antes de crear la
salida. Que falte el registro de una variable es un JSON incompleto; no equivale
a una medición explícitamente declarada ausente. `.gitattributes` mantiene LF
en los JSON/CSV de `data/moon/` para conservar los hashes entre checkouts.

## Pruebas y documentación

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests\lunar
```

Se conservan los 120 casos previos y se agregan 34 de CSV. Cubren igualdad exacta
de todos los valores y estados, ausencias, ceros, trazabilidad, determinismo,
protección de entradas y ejecución sin dependencias científicas. Los casos
previos incluyen pruebas sintéticas y comprobaciones opcionales
contra los IMG locales. Las pruebas locales se omiten si faltan esas entradas;
no requieren descargarlas. pvl 1.3.2 emite una advertencia de deprecación interna
conocida; no se oculta. Las comprobaciones externas QGIS/GDAL siguen pendientes.

- [Definiciones, selección y exclusiones](variables.md).
- [Metodología científica y contrato JSON](lola_methodology.md).
- [Compatibilidad, migración y evidencia](integration.md).

Ninguna salida evalúa la seguridad integral de aterrizaje.
