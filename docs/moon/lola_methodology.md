# Extracción LOLA y contrato JSON — versión 1.0.0

## Alcance y arquitectura

La herramienta lee exclusivamente LDEM_16_FLOAT y LDRM_32_50_FLOAT locales.
El único paquete está en `backend/processing/lunar_data/`; registro y mediciones
compartidas están en `data/moon/`, y las pruebas en `backend/tests/lunar/`.
Los originales siguen en `NASA-Lunar-Studies/data/raw/`. Esta migración conserva
el contrato JSON 1.0.0. La versión 0.2.0 agrega pendiente derivada, sin alterar
elevación o rugosidad y sin endpoints. La vista CSV posterior sólo transforma
el JSON ya generado; no interviene en estos cálculos ni modifica el original.
Las fuentes adicionales Diviner se habilitan mediante `--sources`; los lectores
LOLA y sus resultados no cambian. Véase la guía de fuentes adicionales.
El flujo es: validación de coordenadas y registro → interpretación PDS4/PDS3 →
validación estructural del IMG → lectura puntual de celdas nativas → conversión
física → JSON estricto. No hay descargas, reproyección global ni interpolación
adicional. El comparador terrestre es un componente externo.

- `metadata.py`: usa XML con namespaces y `pvl` para PDS3. Contrasta identidad,
  cuerpo, versiones científicas, unidades, dimensiones, tipo float32 little-endian,
  orden de ejes, offset binario, proyección, orientación, marco y geometría.
- `lola.py`: abre `numpy.memmap` en modo `r`, consume escalares y libera el buffer
  al salir del contexto. No convierte todo el mapa a un array en RAM.
- `export.py`: construye el contrato, calcula SHA-256 por bloques de 1 MiB y
  serializa JSON sin NaN/Infinity. El hash recorre el archivo completo, pero no
  lo carga completo en memoria. Este costo se paga una vez por archivo por ejecución.
- `__main__.py`: recibe un punto o lista de sitios y escribe un archivo nuevo.

El lector valida este subconjunto de PDS; no es un lector universal ni realiza
validación completa contra los esquemas XML de NASA. Productos, proyecciones,
escalas o estructuras incompatibles se rechazan en lugar de interpretarlos por
aproximación. Para estos dos productos se exige escala 1 y los offsets conocidos.

## Archivos originales y referencias

El IMG se toma de `File_Area_Observational/File/file_name`; PDS3 debe apuntar al
mismo nombre. La etiqueta suplementaria se resuelve primero por su nombre
declarado `.lbl`; si no existe, se admite `.lbl.txt`. La comparación de nombres
ignora mayúsculas/minúsculas y rechaza ambigüedades. Se rechazan rutas que salgan
del directorio vecino, incluidos enlaces resueltos fuera de él. No se renombra,
reescribe ni corrige el contenido de ningún original.

La salida usa creación exclusiva: no sobrescribe archivos existentes. También
se verifica que el destino no coincida con las entradas. El JSON se serializa
antes de abrir la salida, por lo que un NaN accidental no genera un archivo
parcial. Un fallo de escritura del sistema operativo aún podría dejar una salida
incompleta; debe repetirse con otro destino después de resolver ese fallo.

## Coordenadas y política de bordes

Entrada: grados de latitud planetocéntrica y longitud positiva hacia el este,
en **Mean Earth/Polar Axis de DE421**, cuerpo Luna, esfera de radio 1737400 m.
No se interpreta una coordenada terrestre EPSG:4326 ni se transforman otros
marcos lunares. Las coordenadas de otras fuentes deben armonizarse antes.

La longitud se normaliza a [0, 360). Las latitudes fuera de [-90, 90] o los
números no finitos se rechazan. Para un raster de `p` píxeles por grado y un
punto que no esté exactamente en un polo:

```text
fila = floor((90 - latitud) * p)
columna = floor(longitud_normalizada * p)
latitud_centro = 90 - (fila + 0.5) / p
longitud_centro = (columna + 0.5) / p
```

Los índices son base cero. En bordes exactos se selecciona la celda hacia el
sur y el este. 360° equivale a 0°. La protección del último índice sólo corrige
redondeo de punto flotante cerca del extremo; no corrige latitudes inválidas.

En **±90° exactos** se devuelve `not_sampled`, `value: null` y el motivo
`exact_pole_not_sampled_longitude_is_degenerate`. Los centros de las grillas no
coinciden con el polo y no se elige una columna arbitraria. Esto es una política
del extractor, no una afirmación de ausencia general de cobertura polar de LOLA.

Se consulta la celda que contiene el punto, no una medición láser exacta en ese
punto ni el píxel más cercano bajo distancia geodésica. Cada variable conserva
su grilla. La pequeña diferencia entre escalas métricas redondeadas y escalas
angulares se evita usando estas últimas para indexar. El ancho superficial
aproximado se estima con `R * Δlongitud_radianes * cos(latitud_centro)`.

## Conversiones y faltantes

**LDEM:** la etiqueta prescribe `HEIGHT = DN * SCALING_FACTOR`. Los valores
están en km y se exportan en m. `value_offset = 1737.4` se conserva como
metadato, pero no se suma: sólo serviría para calcular radio planetario.
Se registra una esfera de referencia, sin afirmar que sea un geoide.

**LDRM:** salida en m según los campos estructurados PDS3/PDS4 y la definición
física. La inconsistencia textual de grados se documenta en `variables.md` y
en cada resultado. No se deriva de LDEM ni se transforma a pendiente.

- NaN e infinitos almacenados → `missing`, valor nulo.
- Constantes especiales declaradas → `missing`, antes de convertir unidades.
  Las constantes finitas se comparan con la representación float32 almacenada.
- Rugosidad negativa → `invalid`, valor nulo, porque una dispersión no puede
  ser negativa.
- Cero y elevaciones negativas → valores válidos si no son constantes declaradas.
- Fuera de mínimos/máximos estadísticos publicados → advertencia, sin eliminar
  automáticamente el valor. Los extremos documentales pueden estar redondeados.

Las etiquetas locales no declaran constantes especiales LOLA: el programa lo
informa y no inventa un sentinel. No puede identificar un faltante codificado
como número finito si no está documentado. `raw_value` conserva un sentinel
finito para auditoría, pero nunca un valor no finito que invalide el JSON.

## Contrato para el resto del equipo

El objeto raíz contiene:

| Campo | Contenido |
|---|---|
| `schema_version` | Versión del contrato; cambios incompatibles requieren una nueva versión mayor |
| `variable_registry_version` | Versión de las decisiones generales y estados |
| `coordinate_reference` | Cuerpo, marco y convenciones |
| `similarity` | `computed: false`, responsabilidad del comparador externo |
| `limitations` | Límites generales de interpretación |
| `reproducibility` | Versiones de Python/NumPy/pvl/código, hashes y configuración |
| `sources` | Productos, versiones PDS y científicas separadas, período, archivos, hashes y conversiones |
| `sites` | Identidad, marca de ejemplo, coordenadas solicitadas/normalizadas y mediciones |

Cada `sites[].measurements` es un diccionario por ID estable del registro:
`elevation`, `roughness` y claves reservadas para variables posteriores o
excluidas. El consumidor debe admitir nuevas claves, consultar los estados y
no asumir que todas las variables participan de la similitud.

| Campo de medición | Semántica |
|---|---|
| `value`, `unit` | Valor convertido o `null`; en procesadores pendientes la unidad es la prevista por el registro |
| `selected_for_project` | Selección científica, independiente de la implementación |
| `implemented` | Existencia de procesador en esta versión |
| `available` | `true`: muestra válida; `false`: ausencia/invalidación conocida; `null`: disponibilidad no evaluada |
| `status`, `reason` | Estado y motivo preciso |
| `used_in_similarity` | Siempre `null`: decisión externa no evaluada |
| `source_ref` | Referencia a `sources`; nula cuando no hay extracción |
| `raw_value`, `raw_unit` | Valor almacenado para auditoría, sólo en procesadores implementados |
| `sampling` | Método, índices, centro y resolución del píxel consultado, o nulo si no se muestreó |
| `quality` | Advertencias y límites; incertidumbre y conteo desconocidos se expresan con `null` |

Estados actuales: `valid`, `missing`, `invalid`, `not_sampled`,
`not_implemented`, `excluded`.

Para Diviner pendiente, estar dentro de ±70° sólo verifica el límite declarado,
no la existencia de una muestra válida: `available` permanece nulo. Fuera de
ese intervalo se puede afirmar `available: false` con motivo
`outside_declared_latitude_coverage`, pero `implemented` sigue siendo falso y
`status` sigue siendo `not_implemented`. Esta comprobación de cobertura no es
un procesador Diviner. Para variables excluidas no se evalúa disponibilidad.

Agregar Diviner o iluminación exigirá implementar su lector, verificar unidades,
escalas y cobertura real, actualizar documentación/registro y añadir pruebas.
Las justificaciones extensas no se repiten en el JSON por sitio; el hash del
registro identifica la versión exacta consultada.

## Reproducción y validación

La salida omite una fecha de ejecución variable y ordena sus claves. Las mismas
entradas, sitios, registro, fuentes de código y versiones de software producen
el mismo JSON. Los nombres de destino no forman parte del resultado. Los
hashes de código y de los archivos locales permiten detectar cambios; no
certifican por sí solos que una copia local coincida con un checksum oficial.

La suite utiliza archivos binarios sintéticos pequeños, etiquetas sintéticas
autocontenidas y pruebas opcionales con los IMG locales. Verifica conversiones,
orden de bytes, orientación, bordes, longitud, polos, faltantes, metadatos
incompatibles, no sobrescritura y estados de variables. La lectura de píxeles
reales se contrasta con un acceso independiente `seek` + `struct.unpack`.

La referencia local verificada en (0°, 0° E), marcada como ejemplo, es:

| Variable | Fila, columna | Centro consultado | Valor |
|---|---|---|---:|
| LDEM | 1440, 0 | −0,03125°, 0,03125° E | −718,6850309371948 m |
| LDRM | 2880, 0 | −0,015625°, 0,015625° E | 0,4296111762523651 m |

Las cifras muestran la decodificación numérica para reproducir pruebas, no
exactitud física. Los metadatos y las pruebas no ofrecen incertidumbre por
píxel. LDRM puede contener interpolación y requiere LDRC para caracterizar el
soporte observacional; LDEM menciona posibles artefactos en límites de bandas.
No se añaden porcentajes de confianza.

No se hizo todavía una comparación espacial externa con QGIS/GDAL ni una
validación científica de campo. Las pruebas independientes de bytes verifican
la lectura binaria, no constituyen por sí solas una verificación independiente
de toda la georreferenciación. Ningún resultado implica seguridad de aterrizaje.

## Referencia antes y después de la migración

En la primera etapa se preservaron los 60 casos originales y los imports públicos
`lunar_data`. `metadata.py`, `lola.py` y `export.py` se trasladaron sin alterar
sus algoritmos. El CLI resuelve
por defecto las rutas del checkout; los argumentos de rutas explícitas se
mantienen. Los primeros registros prepararon fuentes adicionales con valores nulos;
el registro actual 2.0.0 incorpora pendiente y las siete variables seleccionadas. Elevación y rugosidad
conservan sus valores, fuentes y registros completos de medición.

La comparación registra por separado valores almacenados/convertidos, unidades,
coordenadas, centros, índices, advertencias y fuentes. Los hashes de código y
registro pueden cambiar legítimamente. La versión histórica publicada se
conserva en `NASA-Lunar-Studies/examples/lola_measurements.example.json`.
La guía y los pasos para el otro desarrollador están en
[integration.md](integration.md).

## Pendiente derivada de LDEM

Implementada en `lunar_data` 0.2.0, registro 1.2.0. Se adapta el método de
diferencias centrales de **n.x**, commit
[`d6daf40f7e12815f3b83418ce4b5bd6928f0acf8`](https://github.com/akcjsbfifb/NASA-SPACE-CHALLENGE-2026/commit/d6daf40f7e12815f3b83418ce4b5bd6928f0acf8)
de `lola-slope`. La adaptación conserva la fórmula y agrega lectura puntual,
validación, exportación y pruebas; no integra ni modifica su rama.

`LolaRaster.sample_slope(latitude_deg, longitude_deg)` utiliza el mismo LDEM
abierto y la misma selección de celda que `sample()`. Lee cinco escalares:
centro, norte, sur, este y oeste. No calcula pendiente al abrir, no construye
matrices globales y no agrega otro lector. `slope.py` sólo contiene geometría
y matemática escalar, sin operaciones de archivos.

Con alturas en metros, radio R = 1737400 m tomado de los metadatos, paso angular
Δθ y latitud φ del **centro del píxel**, el método 1.0.0 es:

```text
z_m = raw_km * scaling_factor * 1000       (sin sumar OFFSET)
dy = R * radians(Δθ)
dx = dy * cos(radians(φ))
gx = (z_este - z_oeste) / (2 * dx)
gy = (z_sur - z_norte) / (2 * dy)
slope_deg = degrees(atan(hypot(gx, gy)))
```

La derivada norte-sur se orienta hacia el sur; el signo no altera su magnitud.
El centro no participa en la resta, pero se exige su validez. No se implementa
aspecto, Horn, ajuste de plano, suavizado ni derivadas unilaterales.

Las columnas son periódicas: el oeste de la columna 0 es la última columna.
Polos exactos y primera/última fila producen `not_sampled`, `available: false`
y valor nulo, con motivo explícito. En filas extremas sólo se lee el centro;
no se inventa un vecino. Un NaN, infinito o constante especial declarada en
cualquiera de las cinco entradas produce `missing` y pendiente nula. Cero y
alturas negativas son válidos. Valores fuera de estadísticas publicadas generan
advertencia, no una sustitución o descarte automático.

La salida preserva las coordenadas solicitadas y normalizadas, fila/columna,
centros, `dx_m`, `dy_m`, separación entre vecinos opuestos y relación de pasos.
`input_samples` contiene alturas originales, convertidas, unidades, estados y
advertencias de cada entrada. `raw_value` y `raw_unit` de la pendiente son nulos:
no existe una banda NASA original de pendiente en este cálculo. `value` conserva
el ángulo calculado, sin normalizar ni redondear para presentación.
`sources.slope` es una derivación de `sources.elevation`, donde permanecen el
producto, etiquetas, período, URL y hashes originales. El método y su atribución
se registran tanto en fuente como en medición. No se calculan pesos ni similitud.

### Escala y limitaciones

El paso angular es 0,0625°. El paso norte-sur es ≈1895,2094 m y la separación
entre vecinos opuestos ≈3790,4188 m. Estas distancias no son incertidumbre ni
resolución efectiva. En el ejemplo austral, φ = −85,03125°, el paso este-oeste
es ≈164,1486 m y la separación opuesta ≈328,2972 m. El cálculo tiene soporte
anisotrópico: no representa pendiente a una escala física uniforme.

Se advierte en todas las mediciones que el paso longitudinal disminuye hacia
los polos. No se introduce un límite artificial de dx ni un umbral arbitrario
de exclusión por latitud. La disponibilidad numérica no acredita precisión
polar: la división por pasos pequeños amplifica diferencias y errores del DEM.
La esfera de radio constante es una aproximación; no se modelan topografía
subpíxel, obstáculos, incertidumbre del gradiente ni seguridad de aterrizaje.

La pendiente terrestre de ETOPO usa una definición angular semejante, pero
distancias aproximadas, un mínimo dx de 200 m, sustitución de vecinos ausentes
y bordes replicados. Por ello no se habilita automáticamente su comparación.

### Contraste local reproducible

`test_real_slope_independent_five_binary_reads` abre el IMG mediante
`seek` + `struct.unpack`, calcula índices y distancias independientemente y
evalúa `atan(sqrt(gx*gx + gy*gy))*180/pi`, sin llamar a las funciones de
`slope.py`. Tolerancia numérica: 1e-12 grados, no incertidumbre científica.

| Coordenada solicitada | Fila, columna | Pendiente (°) | Independiente (°) | Diferencia absoluta (°) |
|---|---|---|---|---|
| 0°, 0° E | 1440, 0 | 0.1900942345716397 | 0.1900942345716397 | 0 |
| −85°, −10° E | 2800, 5600 | 9.61866522327338 | 9.618665223273384 | 3.55e-15 |

| Altura convertida (m) | Ecuatorial | Austral |
|---|---:|---:|
| Centro | −718.6850309371948 | −351.0236144065857 |
| Norte | −728.7025451660156 | −603.2520532608032 |
| Sur | −718.8617587089539 | −17.284920439124107 |
| Este | −717.0171141624451 | −353.1443178653717 |
| Oeste | −724.847137928009 | −330.34637570381165 |

La suite conserva los 60 casos anteriores con expectativas de pendiente
actualizadas y agrega 60 casos: 120 aprobados con los IMG locales presentes.
Incluye gradientes analíticos, faltantes en cada posición, periodicidad,
geometría, recursos, acceso restringido a cinco escalares y JSON idéntico entre
ejecuciones. Los registros completos previos de elevación y rugosidad, sus
fuentes, coordenadas y los hashes de 17 archivos protegidos coinciden antes y
después. El manifiesto y el contraste detallado quedan localmente en
`NASA-Lunar-Studies/output/slope_integration.*.json`, excluidos de Git.

La concordancia valida esta implementación numérica, no una comprobación
externa del DEM, de la georreferenciación o de la precisión física.
