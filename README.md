# NASA Space Apps Challenge 2026

Repositorio compartido del equipo. Las instrucciones de este README corresponden
al paquete lunar `backend/processing/lunar_data/`; no sustituyen la configuración de los
componentes de frontend, backend o procesamiento terrestre.

## MoonStudies — módulo de datos lunares

Extractor local de **elevación LOLA LDEM 16**, **rugosidad LOLA LDRM 32/50**
y **pendiente derivada del LDEM por diferencias centrales**
para coordenadas lunares. Exporta JSON con unidades, celdas consultadas,
procedencia, hashes y calidad de procesamiento. No calcula similitud terrestre
ni evalúa seguridad de aterrizaje.

El código está en `backend/processing/lunar_data/`. Los IMG y sus etiquetas
permanecen en `NASA-Lunar-Studies/data/raw/`, intactos y excluidos de Git.
El procesamiento es offline: la aplicación puede consumir los JSON pequeños de
`data/moon/` sin abrir los rásteres. Los scripts terrestres no se modifican.

## Instalación en Windows / PowerShell

Desde la raíz de este repositorio, con Python 3.12:

```powershell
# Crear el entorno solamente si no existe .venv:
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-lunar.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .\backend
```

No es necesario activar el entorno ni cambiar la política de ejecución.
`backend/requirements-lunar.lock.txt` fija el entorno de ejecución y pruebas verificado en
Windows con Python 3.12.10. El empaquetador se resuelve mediante `pyproject.toml`.

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

El [JSON histórico publicado](NASA-Lunar-Studies/examples/lola_measurements.example.json)
se conserva sin modificar. Las mediciones LOLA de ambas versiones son iguales;
la nueva registra las rutas actuales y agrega pendiente derivada sin modificar
elevación ni rugosidad. El método y sus límites están en la
[metodología LOLA](docs/moon/lola_methodology.md#pendiente-derivada-de-ldem).

Para compartir una tabla ancha también está disponible
[`lola_measurements.example.csv`](data/moon/lola_measurements.example.csv).
Se genera desde el JSON completo, sin abrir datos NASA ni recalcular valores:

```powershell
.\.venv\Scripts\python.exe -m lunar_data.csv_export --input .\data\moon\lola_measurements.example.json --output .\output\moon_examples.csv
```

Elegir una salida nueva. El [formato CSV](docs/moon/README.md#csv-ancho-desde-el-json)
conserva estados, coordenadas originales y SHA-256 del JSON fuente.

## Datos requeridos para regenerar las mediciones

```text
NASA-Lunar-Studies/
  data/raw/lola/
    ldem/
      ldem_16_float.img
      ldem_16_float.xml
      ldem_16_float.lbl.txt   # también se admite el nombre original .lbl
    ldrm/
      ldrm_32_50_float.img
      ldrm_32_50_float.xml
      ldrm_32_50_float.lbl.txt
```

Se interpretan las referencias de los XML y se resuelve la extensión `.lbl.txt`
sin modificar archivos. Se admiten exclusivamente estos dos productos globales
float, con su geometría y marco DE421. No se descargan datos automáticamente.

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
.\.venv\Scripts\python.exe .\scripts\extract_moon.py `
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
