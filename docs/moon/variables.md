# Registro científico de variables — versión 1.2.0

Este documento explica las decisiones científicas. `data/moon/variables.json`
mantiene identificadores, unidades previstas, fuentes y estados que el extractor
usa para construir la salida. Las justificaciones generales se mantienen aquí
para evitar repetirlas en cada sitio. Cambios científicos requieren actualizar
el registro y su versión; implementar un procesador requiere además código y
validación. Agregar una entrada no crea un procesador.

## Estados independientes

| Concepto | Significado | Representación |
|---|---|---|
| Seleccionada para el proyecto | Forma parte del alcance científico previsto | `selected_for_project` |
| Implementada | El programa puede extraerla y realizar los controles documentados | `implemented` |
| Disponible para el sitio | Hay un valor numéricamente válido en la celda consultada | `available` por medición |
| Utilizada en similitud | El comparador la incorpora con metodología y pesos definidos | `used_in_similarity: null` en este módulo |
| Excluida | Decisión deliberada de no evaluarla en el análisis actual | `scope: excluded` en el registro |
| Opcional operativa | Puede aportar contexto operativo; no integra la similitud terrestre | `scope: optional_operational` |

`available: null` significa que no se evaluó disponibilidad. `false` puede
indicar un faltante, valor inválido, política de muestreo o ausencia conocida de
cobertura; el motivo lo distingue. `true` no equivale a incertidumbre conocida,
observación directa o validación para una misión. El comparador debe consultar
estado, motivo, unidades, advertencias y referencia espacial; no basta con que
la clave exista en JSON. No corresponde asignar cero a variables pendientes.

## Variables seleccionadas

| ID / estado actual | Definición y unidad de salida o prevista | Fuente, cobertura y resolución | Uso previsto y justificación | Limitaciones |
|---|---|---|---|---|
| `elevation` / implementada | Altura respecto de una esfera lunar de radio 1737,4 km; salida en m | LOLA LDEM_16_FLOAT, global; 16 px/°, 0,0625°; ≈1895,21 m en el ecuador | Caracterizar topografía y contexto geomorfológico | No es radio planetario, altura sobre geoide ni nivel del mar terrestre. La elevación sola no determina transitabilidad o seguridad de aterrizaje. No hay detalle subpíxel. |
| `roughness` / implementada | Mediana por celda de la rugosidad estimada a partir de residuos de altura de cinco retornos tras retirar un plano; m | LOLA LDRM_32_50_FLOAT, global; 32 px/°, 0,03125°; ≈947,60 m en el ecuador | Caracterizar irregularidades relevantes para movilidad y operaciones de superficie | La separación nominal entre puntos adyacentes es ≈25 m a 50 km de altitud orbital. El tamaño de celda no define la línea de base de medición. No equivale directamente a TRI terrestre. Sin LDRC no sabemos el número de observaciones ni distinguimos todas las celdas interpoladas. |
| `rock_abundance` / implementada | Fracción de superficie rocosa inferida mediante emisión térmica de rocas y regolito; unidad prevista 1 | Diviner GHRM RA SAM seleccionado; 70° S–70° N, 128 px/°, ≈236,90 m en el ecuador | Contexto superficial relacionado con rocas y obstáculos potenciales | No es un inventario de cada roca ni identifica obstáculos pequeños. Depende del modelo térmico. Fuera de ±70° no hay cobertura de este producto. La codificación/unidad del raster debe validarse al implementar. |
| `bolometric_temperature` / implementada | Temperatura efectiva derivada de observaciones radiométricas, a medianoche ajustada por pendiente; K previstos | Diviner GHRM TBOL SAM seleccionado; 70° S–70° N, 128 px/°, ≈236,90 m en el ecuador | Caracterizar condiciones térmicas nocturnas de referencia | No mide el ciclo completo, amplitud día-noche ni mínimo nocturno absoluto. No es directamente intercambiable con temperatura del aire terrestre. |
| `regolith_temperature` / implementada | Temperatura del componente regolito inferida mediante separación térmica de rocas y regolito, a medianoche ajustada por pendiente; K previstos | Diviner GHRM TREG SAM seleccionado; 70° S–70° N, 128 px/°, ≈236,90 m en el ecuador | Caracterizar térmicamente el componente regolito | Es una inferencia dependiente del modelo; no representa por defecto una profundidad específica ni propiedades térmicas completas. Comparar con TBOL no reconstruye un ciclo térmico. |
| `polar_solar_illumination` / pendiente, complementaria | Estadística de iluminación modelada sobre relieve polar, dependiente del período y producto; fracción normalizada prevista | NASA LOLA/Mazarico, PGDA 69; productos polares con coberturas distintas, incluidas resoluciones de 240, 120 y 60 m/px; producto aún no elegido | Contexto de iluminación y operaciones energéticas | No equivale a irradiancia, potencia eléctrica ni suministro continuo. Deben registrarse período, altura de evaluación, escala y proyección. No se extrapola a zonas sin cobertura. |
| `slope` / implementada, derivada | Inclinación del gradiente del DEM; grados sin normalización | LDEM_16_FLOAT; centro y cuatro vecinos, diferencias centrales; 0,0625°; pasos RΔθ y RΔθ cos(latitud central) | Contexto topográfico a escala de grilla; método adaptado del aporte de n.x | Sin resultado en polos exactos, filas extremas o faltantes. Distancias anisotrópicas, incertidumbre no determinada; no es producto NASA independiente ni garantía de transitabilidad. Comparabilidad terrestre pendiente. |
| `lend_neutron_indicator` / seleccionada, pendiente | Familia de tasas relativas normalizadas, errores y exposiciones ALDE; unidad de RATE pendiente de validar | LEND ALDE, grilla de 1° entre 80° S y 80° N; períodos 2009-09-15–2011-12-11 y 2011-12-11–2016-09-14 separados | Preparar indicadores neutrónicos relacionados con hidrógeno, sin estimar recursos | No hay lector LEND implementado. Mantener canales y períodos separados; no inferir porcentaje de hidrógeno, agua o hielo. |

Las resoluciones métricas cilíndricas citadas son nominales ecuatoriales: el
ancho superficial este-oeste disminuye aproximadamente con cos(latitud). El
programa conserva la resolución angular y muestrea cada raster en su propia
grilla; no crea una malla común artificial.

Los XML Diviner locales describen NaN como faltante y no incluyen una unidad en
`Element_Array`. Las unidades previstas de la tabla son definiciones físicas,
no una certificación de la codificación de los TIFF todavía no procesados.
Los nombres SAM identifican medianoche ajustada por pendiente: usar el producto
no es la fuente de nuestra pendiente: ésta se deriva exclusivamente del LDEM.

## Variables excluidas y contexto operativo opcional

Excluir una variable no significa que sea irrelevante. Estas decisiones limitan
lo que podemos concluir y deben acompañar cualquier presentación del proyecto.

| Variable / qué representa | Relevancia científica u operativa | Motivo de exclusión actual | Limitación resultante | Fuente o procedimiento futuro |
|---|---|---|---|---|
| Mineralogía: composición mineral, abundancias o indicadores espectrales | Geología y recursos para utilización in situ | Requiere productos adicionales, interpretación espectral y armonización | No identificamos composiciones favorables ni potencial minero | Seleccionar espectrometría orbital, por ejemplo M³/Chandrayaan-1 o Kaguya MI, y documentar calibración, cobertura y metodología; no hay un producto seleccionado en esta entrega |
| Hielo y disponibilidad de agua: presencia, abundancia y accesibilidad, que no son equivalentes | Recursos y sostenibilidad de futuras bases | Necesita fuentes específicas y una interpretación científica diferente | No podemos identificar reservas, disponibilidad ni viabilidad de extracción. El frío o la sombra por sí solos no prueban agua | Evaluación conjunta de productos de volátiles/neutrones y evidencias complementarias. Hidrógeno no equivale por sí solo a hielo ni a agua accesible; requiere estudio y selección de fuentes |
| Visibilidad directa de la Tierra: fracción/condición geométrica de visibilidad del disco terrestre | Contexto de comunicaciones | Excluida de la similitud terrestre por falta de equivalencia física; incorporación operativa opcional, todavía no implementada | No evaluamos cobertura de comunicaciones ni disponibilidad de enlaces | Mapas de Earth visibility de PGDA 69; después, modelo de enlaces, estaciones, geometría temporal y requisitos de la misión |
| Sky Visibility: ángulo sólido de cielo libre de obstrucción por relieve, típicamente sr | Geometría de exposición y operaciones específicas | Fuera del alcance y del procesamiento inicial | No caracterizamos la obstrucción global del cielo ni sus consecuencias operativas | Productos de Sky Visibility de PGDA 69, con validación de unidad, normalización y resolución del producto elegido |
| Evaluación integral de seguridad de aterrizaje: evaluación de peligros y restricciones para un vehículo y misión | Condición necesaria para seleccionar un sitio de aterrizaje real | Las variables y resoluciones del módulo son insuficientes para esa tarea | No se puede declarar un sitio seguro, apto ni certificado para aterrizar a partir de nuestros resultados | Estudio independiente con topografía y obstáculos a escala adecuada, pendientes, requisitos del vehículo, navegación, iluminación y otras restricciones de misión |

## Unidades LDRM: decisión y evidencia

En la etiqueta PDS3 local, el bloque `IMAGE` declara `UNIT = METER` y describe
cada muestra como rugosidad en metros. El XML PDS4 también declara `METER` en
`Element_Array` y metros en la descripción del array. Además, la definición
matemática es una dispersión de residuos de altura: una longitud.

Sin embargo, un párrafo de la descripción general dice que los valores están
en grados. La contradicción también está en el texto descriptivo del XML, por
lo que migrar a PDS4 no la resuelve. La implementación usa **metros**, apoyada en
los campos estructurados coincidentes y la definición física, y exporta
`ldrm_unit_text_conflict_resolved_as_meters`. No se aplica conversión a grados.
No encontramos una fe de erratas específica que permita eliminar la
advertencia; no presentamos el texto contradictorio como corregido por NASA.

El sufijo `50` representa cuantil 0,50, no una línea de base de 50 metros. La
etiqueta describe una corrección a una altitud orbital de referencia de 50 km y
una separación nominal de puntos adyacentes de 25 m; estas magnitudes no deben
confundirse con la resolución de la grilla.

## Fuentes y límites del alcance

- [LOLA LDEM: XML oficial](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/ldem_16_float.xml) y etiqueta PDS3 vecina; copias locales sin modificar en `data/raw/lola/ldem/`.
- [LOLA LDRM: XML oficial](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/float_img/ldrm_32_50_float.xml) y etiqueta PDS3 vecina; copias locales en `data/raw/lola/ldrm/`.
- [LOLA RDR/GDR Software Interface Specification](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/document/rdrsis.htm), para contexto de productos y coordenadas; la interpretación concreta se contrasta con las etiquetas de cada producto.
- [Diviner GHRM: catálogo oficial y etiquetas de cada producto](https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_ghrm/geotiff/). Copias XML locales bajo `data/raw/lola/diviner/`; no hay TIFF procesados en esta entrega.
- [NASA Lunar Polar Illumination / PGDA 69](https://pgda.gsfc.nasa.gov/products/69), incluye iluminación, visibilidad terrestre y del cielo. Ofrece COG; todavía no se seleccionó ni procesó un producto polar.
- [Derivación radiométrica de temperatura del regolito y abundancia de rocas](https://doi.org/10.1002/2017JE005387), como contexto del modelo; verificar además la documentación específica de GHRM antes de implementar.

El PDF de la hackatón propone una arquitectura más amplia. En esta entrega no
implementamos Marte, recursos, extracción regional, un modelo ML ni
el comparador. Las métricas terrestres necesitan armonización física y de
escala: la presencia de dos números con la misma unidad no demuestra que sean
comparables. Cualquier porcentaje futuro debe indicar variables efectivamente
usadas, faltantes y metodología. Este módulo no fija ni renormaliza pesos.

## Preparación de fuentes posteriores a la migración

Pendiente ya no es una exclusión definitiva del proyecto: está seleccionada y
en desarrollo externo. `implemented: false` se refiere al procesador actual;
`implementation_status` registra la coordinación pendiente. El JSON histórico
conserva el registro 1.0.0 y su antigua exclusión; el registro mantenido es 1.1.0.
La ausencia de mediciones nunca indica condiciones favorables.

Los seis originales LEND siguen en
`NASA-Lunar-Studies/data/raw/lola/lend/`. Cada DAT tiene 57600 registros de
310 bytes (17856000 bytes), con floats big-endian y campos temporales ASCII.
Su XML describe STN1–3, SETN, CSETN combinado y 16 elementos SHEN con tasas,
errores y exposiciones. Los elementos SHEN incluyen sumas superpuestas y no se
suman indiscriminadamente. SETN y CSETN son candidatos de estudio epitérmico;
no se eligió una conversión a hidrógeno. Las exposiciones escalares tienen unidad
s; RATE/ERR no declaran una unidad explícita en esos XML. El FMT referenciado por
PDS3 no acompaña estas copias, aunque los XML describen los campos. Se necesita
un lector específico y validación del marco, NoData y soporte de observaciones.
La resolución de la grilla no es la resolución instrumental. No se promedian
los períodos ni se genera disponibilidad de agua. Fuente:
[NASA/PDS LEND](https://pds-geosciences.wustl.edu/missions/lro/lend.htm).

La pendiente derivada de LDEM y la vista CSV del JSON ya están implementadas.
Diviner RA/TBOL/TREG SAM ya se leen con ventanas, unidades contrastadas con
el SIS v1.21 §11.1 y NaN declarado por PDS. LEND, iluminación y normalización
permanecen pendientes. El registro actual es 1.3.0.
El registro puede ampliarse sin crear procesadores.
La lectura remota de Diviner respondió 206 para tres rangos de 32 bytes durante
la inspección previa; una ventana Rasterio/GDAL y su costo de transferencia
siguen sin verificarse. Iluminación mantiene preferencia futura por COG.

Las rutas `data/raw/...` citadas arriba se refieren a entradas bajo
`NASA-Lunar-Studies/`, que se conservan localmente. Para ejecutar desde la raíz
consultar [la guía actual](README.md).
