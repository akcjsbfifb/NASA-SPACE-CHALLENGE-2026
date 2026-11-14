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
CSV, Diviner, iluminación, LEND y normalización quedan para otras etapas.

## Pruebas y documentación

```powershell
.\.venv\Scripts\python.exe -m pytest .\backend\tests\lunar
```

Se conservan los 60 casos originales (adaptando las expectativas del estado de
pendiente) y se agregan 60 casos, con pruebas sintéticas y comprobaciones opcionales
contra los IMG locales. Las pruebas locales se omiten si faltan esas entradas;
no requieren descargarlas. pvl 1.3.2 emite una advertencia de deprecación interna
conocida; no se oculta. Las comprobaciones externas QGIS/GDAL siguen pendientes.

- [Definiciones, selección y exclusiones](variables.md).
- [Metodología científica y contrato JSON](lola_methodology.md).
- [Compatibilidad, migración y evidencia](integration.md).

Ninguna salida evalúa la seguridad integral de aterrizaje.
