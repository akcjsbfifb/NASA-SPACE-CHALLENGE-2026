# Registro científico lunar — versión 2.0.0

Registro mantenido: `data/moon/variables.json`; contrato JSON estructural 1.0.0.
Se distinguen selección de una variable, implementación de su lector,
disponibilidad en cada sitio y uso real en similitud. `used_in_similarity: null`
no autoriza un puntaje; lo decide un comparador coordinado. No se inventan pesos.

## Siete variables principales

| Campo | Definición y unidad | Fuente y escala | Limitaciones |
|---|---|---|---|
| `elevation` | Altura sobre esfera lunar de radio 1737,4 km; m | LOLA LDEM_16_FLOAT, 16 px/° | No equivale a elevación terrestre sobre geoide/nivel del mar; raw km × scale ×1000, sin sumar radio. |
| `roughness` | Mediana de rugosidad de residuos de cinco retornos después de retirar un plano; m | LOLA LDRM_32_50_FLOAT, 32 px/° | Baseline nominal entre puntos ≈25 m a 50 km orbitales; no es RMS terrestre de grilla 3×3. Sin LDRC no se conoce soporte por celda. |
| `slope` | Ángulo del gradiente del LDEM; grados | Diferencias centrales, centro y cuatro vecinos, 0,0625° | Métrica esférica; dx disminuye con latitud, sin resultado en filas extremas, polos exactos o faltantes; no prueba seguridad. |
| `rock_abundance` | Fracción superficial rocosa inferida; 1 | Diviner GHRM RA SAM, 128 px/°, ±70° | No es catálogo de obstáculos ni clase litológica terrestre; sin extrapolación polar. |
| `bolometric_temperature` | Temperatura bolométrica nocturna; K | Diviner GHRM TBOL SAM, 128 px/°, ±70° | No es temperatura del aire ni ciclo térmico completo. |
| `regolith_temperature` | Temperatura inferida del componente regolito; K | Diviner GHRM TREG SAM, 128 px/°, ±70° | Modelo distinto de TBOL; no implica temperatura a una profundidad determinada. |
| `hydrogen_abundance_ppm` | Abundancia estimada de H por peso; ppm | Lunar Prospector Hydrogen_halfdeg, grilla 0,5°, DAT /10 contrastado con ASCII | Contextual: no agua/hielo confirmado ni equivalente automático terrestre. Faltantes y negativos no son concentraciones válidas; fiabilidad limitada en zonas ricas en Th/tierras raras. |

El CSV consolidado `lunar_measurements.example.csv` tiene estas siete magnitudes
en columnas `elevation_m`, `roughness_m`, `slope_deg`, `rock_abundance_fraction`,
`bolometric_temperature_K`, `regolith_temperature_K`, `hydrogen_abundance_ppm`.
No hay normalización de rugosidad ni otro comparador o catálogo.

## Unidades y calidad

LDRM presenta una contradicción de texto: su descripción general menciona grados,
pero PDS3 `UNIT=METER`, PDS4 `Element_Array=METER` y la definición física indican
metros. Se usan metros y se conserva la advertencia, sin corregir las etiquetas.
El sufijo 50 es cuantil 0,50, no baseline de 50 m.

Los XML GHRM no declaran unidad en `Element_Array`: el SIS Diviner v1.21 §11.1,
página 69 confirma RA fracción 0–1 y TBOL/TREG Kelvin. SAM significa medianoche
ajustada por pendiente; no ciclo térmico ni mínimo absoluto. Se respeta NaN del
XML, aunque el TIFF no declara NoData GDAL. La cobertura es 70°S–70°N.

Hydrogen_halfdeg declara ppm por peso en el ASCII. La comparación de 259200
celdas verifica orientación sur-norte, signed int16 MSB y escala ÷10. Se usa
ASCII para distinguir `**********` de un cero válido, porque ambos pueden
codificarse 0 en DAT. Las estimaciones negativas quedan inválidas con crudos
conservados. La tolerancia de cuantización 0,100001 ppm no es precisión física.
Estos productos especiales distribuidos por NASA no son un archivo PDS revisado
por pares. No se asigna certeza adicional por tratarse de una fuente oficial.

Grilla angular y resolución instrumental efectiva son conceptos distintos.
La realización concreta del marco fijo lunar no siempre está declarada en las
fuentes; no se afirma una alineación externa validada. Las comprobaciones de
bytes y coordenadas son internas, sin validación de campo ni calibración externa.

## Fuentes complementarias o excluidas

- Iluminación polar LOLA/Mazarico: complementaria, no implementada y fuera del
  puntaje principal. No es iluminación global ni potencia, temperatura o albedo.
  Falta de medición no significa oscuridad permanente; no se descarga en esta entrega.
- Visibilidad de la Tierra: opcional operativa, no equivalente terrestre para similitud.
- Mineralogía, agua/hielo accesible, sky visibility y seguridad integral de
  aterrizaje: excluidas del procesamiento actual. H estimado no las implementa.

Fuentes: [LOLA/PDS](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/document/rdrsis.htm),
[Diviner SIS](https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/document/Diviner_RDR_SIS.pdf),
[Lunar Prospector](https://pds-geosciences.wustl.edu/missions/lunarp/reduced_special.html),
[PGDA polar](https://pgda.gsfc.nasa.gov/products/69).
