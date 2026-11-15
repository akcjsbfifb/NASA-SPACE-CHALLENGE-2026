# Procesamiento lunar y datos compartidos

Paquete único: `backend/processing/lunar_data/`, versión 0.3.0. No incorpora
comparador, catálogo ni endpoints. Dos sitios `*_test_only` siguen siendo
ejemplos; los seis alunizajes Apolo viajan en `apollo_measurements.json` y
`.csv` con lecturas LOLA, Diviner e hidrógeno. Las coordenadas fueron facilitadas
por el usuario y contrastadas por redondeo con el catálogo DE421 de NASA:
https://nssdc.gsfc.nasa.gov/planetary/lunar/lunar_sites.html.
Iluminación polar permanece complementaria y pospuesta.

Para el servicio `/moon`, `LUNAR_DATA_ROOT` indica la carpeta que contiene
`ldem`, `ldrm` y `diviner`; `LUNAR_HYDROGEN_ROOT` indica la carpeta con los
archivos DAT y TXT de Lunar Prospector. Sin estas variables se usa `data/raw/`.
Diviner remoto requiere `LUNAR_DIVINER_REMOTE=1`; si hay un TIFF local junto a
su XML se usa el archivo local. La consulta remota comparte 16 MiB y un plazo
de ocho segundos para iniciar y esperar solicitudes entre los tres productos;
el tiempo total de una lectura en curso no está garantizado. Un error conserva
LOLA e hidrógeno.
La caché de puntos está limitada a 64 resultados, sin guardar errores de fuente.

El buscador terrestre requiere coordinación: el promedio ponderado limita el
denominador a uno incluso con suma de pesos inferior a uno; el tratamiento
polar de pendiente limita la distancia longitudinal; y la rugosidad terrestre
usa RMS de vecinos, mientras LOLA retira un plano. La respuesta terrestre
redondea valores y no incluye todas las fuentes ni estados por candidato.
Se necesitan valores originales y procedencia antes de presentarlos como crudos.

## Consumir los resultados sin datos NASA

En `data/moon/` se publican:

- `lola_measurements.example.json`: documento científico completo, con siete
  variables, unidades, valores originales, estados, métodos, fuentes y hashes.
- `lunar_measurements.example.csv`: tabla consolidada, 33 columnas y una fila
  por sitio, con las siete variables y sus estados.
- `lola_measurements.example.csv`: vista core de 17 columnas que conserva la
  interfaz anterior de elevación, rugosidad y pendiente.
- `validation.diviner.json` y `validation.hydrogen.json`: evidencia ejecutada,
  diferenciando consistencia binaria de validación geodésica/científica externa.

Para leer JSON/CSV no hay que instalar Rasterio ni descargar originales:
Python `json`/`csv` o el lector equivalente del adaptador son suficientes.
`source_json_file` y `source_json_sha256` vinculan cada fila al JSON completo.
Consultar `available`, `status`, `reason` y advertencias antes de usar un número.
Nulo no es cero ni condición favorable. `used_in_similarity: null` no autoriza
a asignar peso; hidrógeno es contextual, sin equivalente terrestre validado.

Los presets de actividad del buscador terrestre están en `activity-presets.md`:
son importancia relativa y valores de búsqueda de un MVP, no mediciones.

## Instalación y extracción desde PowerShell

Desde la raíz del repositorio, Python 3.12:

```powershell
# Sólo si no existe el entorno:
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-lunar.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .\backend
```

Para generar nuevas mediciones Diviner, instalar también el entorno opcional:

```powershell
.\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-lunar-geospatial.lock.txt
.\.venv\Scripts\python.exe -m lunar_data --sources .\data\moon\sources.example.json --sites .\backend\tests\lunar\fixtures\sites.example.json --output .\output\moon.json
```

Las salidas deben ser nuevas: no se sobrescriben entradas ni resultados.
Sin `--sources` no hay acceso de red; las fuentes adicionales aparecen como
`processor_not_configured`. El script `backend/scripts/extract_moon.py` delega al mismo CLI.
Las rutas de configuración se resuelven contra la raíz del checkout editable.

Los originales permanecen ignorados, sin modificar:

```text
data/raw/lola/ldem/ldem_16_float.{img,xml,lbl.txt}
data/raw/lola/ldrm/ldrm_32_50_float.{img,xml,lbl.txt}
data/raw/lola/diviner/<variable>/*.xml
data/raw/lunar_prospector/hydrogen/hydrogenhd.dat
data/raw/lunar_prospector/hydrogen/hydrogenhd.txt
```

`sources.example.json` selecciona Diviner y Lunar Prospector. Cada fuente Diviner
permite `raster` local o HTTPS; no cambia su lógica científica. El transporte
remoto comparte un límite de 16 MiB por ejecución, exige HTTP 206 con rangos
exactos y rechaza respuestas completas. Sus hashes cubren rangos recibidos,
no el TIFF completo. La evidencia guardada verificó los tres productos con
1376256 bytes de cuerpos HTTP, excluyendo cabeceras/TLS. La reconstrucción
de los ejemplos usa esa referencia local verificada; no repite HTTP.

## CSV ancho desde el JSON

```powershell
.\.venv\Scripts\python.exe -m lunar_data.csv_export --input .\data\moon\lola_measurements.example.json --profile full --output .\output\moon.csv
```

`--profile core` (por defecto) conserva 17 columnas. `full` tiene 33:
`site_id`, `latitude_deg`, `longitude_deg`, los siete valores, tres columnas
`<variable>_status`, `<variable>_available`, `<variable>_reason` por magnitud,
y `source_json_file`, `source_json_sha256`. El valor nuevo se llama
`hydrogen_abundance_ppm`. Coordenadas solicitadas, ids y orden se conservan;
−10° no se sustituye por 350°. El marco y la normalización están en el JSON.

UTF-8 sin BOM, coma, punto decimal, LF, sin redondeo ni normalización de valores.
El módulo `csv` escapa campos. `available` es `true`, `false` o vacío si es
desconocido. Valor no disponible y motivo nulo son celdas vacías; cero válido
se conserva. Se rechazan unidades o estados contradictorios. `.gitattributes`
mantiene LF en JSON/CSV de `data/moon/` para estabilizar sus hashes en Windows.
Guardar desde una planilla puede alterar números y bytes; importar como UTF-8/coma.
El JSON sigue siendo la autoridad científica; compartirlo junto con el CSV.

## Lunar Prospector: hidrógeno estimado en ppm

Fuente: [NASA/PDS special products](https://pds-geosciences.wustl.edu/missions/lunarp/reduced_special.html),
producto `Hydrogen_halfdeg`, archivo de diciembre de 2001 publicado el 3-1-2002.
La cabecera ASCII declara **H ppm por peso**. Es una inferencia de datos
neutrónicos corregidos, no porcentaje de agua, hielo ni reserva accesible.
NASA advierte menor fiabilidad en zonas con alto torio y tierras raras y
aclara que esta distribución especial no es un archivo PDS revisado por pares.

La auditoría verificó 259200 celdas, 720 columnas y 360 filas. DAT: 518400 bytes,
enteros **signed int16 big-endian**, valor ppm = raw / 10. El ASCII verifica
límites de cada celda y signo; no se adivina el tipo firmado a partir de un único
píxel. Filas de sur a norte, columnas de −180° a 180° este positivo. Cada celda
mide 0,5°: centros iniciales −89,75° y −179,75°, deducidos de límites ASCII,
no de la frase aproximada del catálogo sobre los extremos de imagen.

En un borde se elige la celda norte/este. El antimeridiano es periódico y los
polos exactos no se muestrean por degeneración de longitud. No se interpola.
Cada consulta lee dos bytes DAT y un registro ASCII de 55 bytes, usando su
cabecera detectada (401 bytes en el original). La referencia ASCII es necesaria:
hay un `**********` en fila 266, columna 667 (43°–43,5°N, 153,5°–154°E) cuyo
DAT vale 0. No existe un NoData binario universal 0: hay 36 celdas no negativas
válidas codificadas también como cero. Se preservan esos ceros válidos.

Hay 4180 estimaciones ASCII negativas. Se retienen raw y referencia ASCII,
pero `value: null`, `available: false`, `status: invalid`: no se publican como
concentraciones físicas. El asterisco produce `missing`. Una discrepancia
binario/ASCII superior a 0,100001 ppm también produce `invalid`.

El binario tiene cuantización de 0,1 ppm; el ASCII conserva más decimales.
El máximo desacuerdo observado es 0,10000000000002274 ppm, consistente con
esa cuantización y el formato decimal. Esa tolerancia numérica **no** es
incertidumbre física. El JSON conserva ambos valores y su diferencia.
No se afirma resolución efectiva de 0,5° ni se asigna incertidumbre por píxel:
la grilla no sustituye a la respuesta espacial y al modelo de calibración.

## Validación local y reproducibilidad

```powershell
.\.venv\Scripts\python.exe -m lunar_data.validation --hydrogen --sources .\data\moon\sources.example.json --sites .\backend\tests\lunar\fixtures\sites.example.json --output .\output\hydrogen_validation.json
.\.venv\Scripts\python.exe -m pytest .\backend\tests\lunar -q
```

La validación recorre el ASCII y el DAT por streaming, verifica todos los
límites, valores, orden MSB y escala con `int.from_bytes`, separado del lector
puntual `struct.unpack`. Las pruebas buscan también intervalos ASCII por
coordenadas para ecuador, ambos hemisferios, antimeridiano, polos cercanos,
bordes, centros, negativos, ceros y la celda faltante.

Los tests de consolidación reconstruyen los ejemplos con LOLA y Lunar Prospector
locales y `validation.diviner.json` verificado, bloqueando HTTP. Comparan los
CSV byte a byte y las seis mediciones anteriores exactamente. El hash de la
evidencia reutilizada figura en la procedencia. Cambios de librerías o bytes
del código pueden cambiar la procedencia sin cambiar la medición: se distinguen.
La validación binario/ASCII no recalibra los neutrones ni verifica externamente
la georreferenciación. La advertencia conocida de deprecación `pvl` se conserva.

Definiciones: [variables.md](variables.md). Metodología LOLA:
[lola_methodology.md](lola_methodology.md). Coordinación con Nico:
[integration.md](integration.md). Ningún resultado acredita seguridad de aterrizaje.
