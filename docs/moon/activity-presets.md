# Presets de actividad

Estos presets no son mediciones. No los cites como valores lunares ni como
pesos publicados. Sirven para un MVP: eligen qué variables importan más y desde
qué valor se busca un análogo terrestre. El porcentaje que sale de esa búsqueda
sigue siendo tentativo.

## Qué es un dato y qué no

Cada preset tiene dos bloques que no significan lo mismo.

`weights` no sale de ningún paper. Es importancia relativa elegida para este
MVP, en la escala 0 a 1. 0 deja la variable afuera.

`search` es el valor que se consulta cuando quien busca no pasa otro. Puede
tener un número aunque no exista una medición lunar de esa magnitud. `measured`
dice cuáles de esos valores salen de la fuente citada. Los que no están en
`measured` los elegimos nosotros para poder buscar. Ningún valor de `search` es
una afirmación sobre la Luna.

Magnitudes que este catálogo no finge tener:

- `tmin_c` es la temperatura del mes más frío en la Tierra. No es la noche
  lunar ni un experimento de flujo de calor.
- `roughness_m` es la rugosidad de la celda terrestre. No es un obstáculo
  lunar en centímetros ni un índice 0 a 1.
- `ice_thickness_m` es espesor de hielo terrestre. No es la profundidad a
  la que el hielo polar lunar sería estable.
- El código de roca es una clase USGS/GLiM de la Tierra usada como analogía.
  No es la clasificación de la muestra lunar.

## Presets

`rover_wheels`. LRV de Apolo 15, 16 y 17 (1971–1972), basalto de mare.
Pesos nuestros: pendiente 0.5, rugosidad 1, roca 1, temperatura 0, hielo 0.
Valores de búsqueda nuestros: pendiente 8°, rugosidad 20 m, roca `vb`. Ninguno
es una medición lunar. Fuente de la actividad, no de los números: misiones
Apolo 15–17.

`landing_site`. Elección de sitio de alunizaje, sin misión única.
Pesos nuestros: pendiente 1, rugosidad 1, resto 0.
Valores de búsqueda nuestros: pendiente 10°, rugosidad 15 m. No se copió el
límite de 10° del HLS ni el de 12° de Chandrayaan-3: son requisitos de
ingeniería, no una medición para la grilla terrestre. Que el número coincida
con el del HLS es casualidad de rango, no una cita.

`polar_ice`. LCROSS (2009) y Chandrayaan-1 M3 (2008–2009).
Pesos nuestros: temperatura 1, hielo 1, resto 0.
Valores de búsqueda nuestros: temperatura −140 °C, hielo 1 m. El hielo que
vieron esas misiones no es `ice_thickness_m`, así que no hay target medido.
−140 °C se elige por debajo del percentil frío terrestre a propósito: la
búsqueda compara contra las celdas más frías, no contra −140 °C absolutos.

`sample_basalt`. Muestreo de basalto de mare en Apolo 11, 12, 15 y 17.
Pesos nuestros: roca 1, pendiente 0.3, rugosidad 0.2, temperatura 0, hielo 0.
Valores de búsqueda nuestros: pendiente 5°, rugosidad 10 m, roca `vb`.

`floor_sample`. No tiene una misión fuente. Es el caso de extraer y
analizar el piso. Pesos nuestros: pendiente 0.3, rugosidad 1, roca 1,
temperatura 0, hielo 0. Valores de búsqueda nuestros: pendiente 3°,
rugosidad 5 m. Target de roca `null` a propósito: el tipo de piso entra solo
si quien busca pasa un código. No se eligió un basalto por defecto.

`viper_ice_prospect`. VIPER, requisito de movilidad de 2022.
De la fuente se tomó un solo número: pendiente 15°. En el paper es el
límite Level 3 del rover (±15°, 40% de deslizamiento), no la pendiente
medida de un sitio ni un análogo terrestre. Por eso `measured: slope`.
https://ntrs.nasa.gov/api/citations/20220000441/downloads/viper-mobility-2022-01-27.pdf
Pesos nuestros: pendiente 0.6, rugosidad 0.5, temperatura 0.8, hielo 1, roca 0.
Valores de búsqueda nuestros: rugosidad 20 m, temperatura −140 °C, hielo 1 m.
Los 20 cm de obstáculo y los 50–100 cm de hielo estable del PDF no son
`roughness_m` ni `ice_thickness_m`, así que no están en `measured`.

`artemis_polar_landing`. Artemis III, requisitos del HLS hacia 2024.
De la fuente se tomó un solo número: pendiente 10°. En el PDF es el
requisito "Surface slope for landing (100m): <10 deg", no una pendiente
medida. Por eso `measured: slope`.
https://ntrs.nasa.gov/api/citations/20240009596/downloads/ArtemisHLSUpdate_2024.pdf
Pesos nuestros: pendiente 1, rugosidad 0.8, hielo 0.5, temperatura 0, roca 0.
Valores de búsqueda nuestros: rugosidad 15 m, hielo 1 m.

`sample_pyroclastic`. Apolo 17, cráter Shorty, 1972, suelo 74220.
La fuente lo identifica como vidrio piroclástico. El código `py` es la
clase terrestre, no el nombre de la muestra.
https://curator.jsc.nasa.gov/lunar/lsc/74220.pdf
Pesos nuestros: roca 1, rugosidad 0.2, resto 0.
Valores de búsqueda nuestros: rugosidad 8 m, roca `py`.

`spa_norite`. Chang'e 4, Yutu-2, Von Kármán, 2019.
La fuente describe una norita con olivino. El código `pb` es la clase
terrestre que nombra norita, gabro y peridotita. No es anortosita y no es
basalto `vb`.
https://doi.org/10.1093/nsr/nwz183
Pesos nuestros: roca 1, rugosidad 0.5, pendiente 0.3, temperatura 0, hielo 0.
Valores de búsqueda nuestros: pendiente 4°, rugosidad 8 m, roca `pb`.

`hadley_rille`. Apolo 15, Hadley Rille, 1971.
De la fuente se tomó un solo número: pendiente 25°. El procedimiento de
vuelo dice que la pendiente aproximada del costado del rille es ~25°.
No es una medición de la grilla terrestre. Por eso `measured: slope`.
https://www.apollojournals.org/alsj/a15/a15lsp.pdf
Pesos nuestros: pendiente 1, rugosidad 0.6, roca 0.8, temperatura 0, hielo 0.
Valores de búsqueda nuestros: rugosidad 12 m, roca `vb`.

`surveyor_regolith`. Surveyor 3 (1967) y Surveyor 7 (1968), mecánica del suelo.
La fuente trata suelo granular. El código `su` es sedimento suelto terrestre.
https://doi.org/10.1029/JB076i032p07833
Pesos nuestros: roca 1, rugosidad 0.5, pendiente 0.4, temperatura 0, hielo 0.
Valores de búsqueda nuestros: pendiente 3°, rugosidad 6 m, roca `su`.
Los newtons por centímetro cuadrado de esa fuente no son una variable del
score.

`light_mantle`. Apolo 17, Light Mantle, testigo 73001/2, 1972.
Depósito no consolidado en pendiente. Código `su`.
https://doi.org/10.1029/2024je008556
Pesos nuestros: pendiente 0.9, roca 0.8, rugosidad 0.4, temperatura 0, hielo 0.
Valores de búsqueda nuestros: pendiente 15°, rugosidad 10 m, roca `su`.
No hay grados publicados para la cara del macizo en esa fuente: 15° es
nuestro valor de búsqueda, no una cita.
