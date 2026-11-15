# Lectores terrestres independientes

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

## Comparación térmica exploratoria

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

## Revisión de pendiente

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
