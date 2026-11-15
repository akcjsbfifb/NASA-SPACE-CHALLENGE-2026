# Mediciones LOLA publicables

Esta es la publicación histórica: el JSON vecino se conserva byte a byte.
La versión mantenida está en [`data/moon/`](../../data/moon/lola_measurements.example.json),
con [instrucciones actuales](../../docs/moon/README.md) y el registro de variables
actualizado. No hay un segundo procesador en esta carpeta.

`lola_measurements.example.json` contiene mediciones reales extraídas de los IMG
locales originales, para los puntos ahora conservados como fixture en
`backend/tests/lunar/fixtures/sites.example.json`. Es un
archivo pequeño para que frontend y comparador prueben el contrato sin instalar
Python ni descargar los mapas. No contiene datos sintéticos ni los mapas completos.

Las coordenadas son **ejemplos**, no sitios de misión seleccionados. Cada registro
lo declara mediante `is_example: true`. Para publicar sitios definitivos, el
equipo debe proporcionar sus coordenadas y marco lunar, registrarlos como tales
y ejecutar una extracción nueva; no hay que renombrar estos ejemplos como sitios
reales seleccionados.

| ID | Latitud | Longitud este de entrada | Elevación (m) | Rugosidad (m) |
|---|---:|---:|---:|---:|
| `equatorial_test_only` | 0° | 0° | −718,6850309371948 | 0,4296111762523651 |
| `southern_high_latitude_test_only` | −85° | −10° | −351,0236144065857 | 0,3567740023136139 |

La longitud −10° se normaliza a 350° E. La elevación está referida a una esfera
lunar de radio 1737400 m. Cada variable se consulta en su celda nativa y conserva
sus índices, centro y resolución: no es una medición láser exacta sobre el punto
solicitado. La cantidad de decimales permite reproducir la decodificación, no
representa exactitud física. La rugosidad conserva la advertencia de unidades
documental y no equivale directamente a la rugosidad terrestre calculada con DEM.

## Uso por otros módulos

El JSON raíz contiene `sites`, `sources`, `coordinate_reference` y
`reproducibility`. Para cada sitio:

- Consultar `site.measurements.elevation` y `site.measurements.roughness`.
- Usar `value` cuando `status === "valid"` y `available === true`; comprobar `unit`.
- Conservar los motivos de ausencia y las advertencias de `quality`.
- Seguir `source_ref` hacia `sources` para consultar producto, conversión y hashes.
- No convertir los valores nulos en cero ni inferir mediciones para variables
  pendientes o excluidas. `available: null` significa disponibilidad no evaluada.
- `used_in_similarity: null` no autoriza a incluir la variable en un puntaje: el
  comparador define y documenta esa metodología.

Diviner e iluminación no están procesados. Fuera de la cobertura conocida de
Diviner, el JSON indica la ausencia de cobertura; dentro, no presupone que haya
una medición válida. La presencia de sus claves prepara el contrato futuro.

El frontend y el comparador remotos todavía requieren una adaptación a este
contrato. Este commit publica los datos y su guía; no cambia esos componentes.

## Regeneración con los IMG locales

Desde la raíz del repositorio en PowerShell, con el entorno y datos ya instalados:

```powershell
.\.venv\Scripts\python.exe -m lunar_data `
  --data-root .\NASA-Lunar-Studies\data\raw\lola `
  --registry .\data\moon\variables.json `
  --sites .\backend\tests\lunar\fixtures\sites.example.json `
  --output .\NASA-Lunar-Studies\output\lola_measurements.regenerated.json
```

La salida debe ser un archivo nuevo. Antes de actualizar el ejemplo publicado,
comparar mediciones, hashes de datos, configuración y código, y revisar el diff.
Una diferencia de versión o de bytes de entrada puede cambiar la trazabilidad;
no hay que eliminar esa información para hacer coincidir los archivos.

La carpeta `examples/` contiene este ejemplo revisado que se comparte mediante
Git. Las ejecuciones ordinarias siguen en `output/`, que está ignorada. Los IMG,
TIFF, entornos, cachés y el PDF de planificación permanecen fuera de Git.

Ver también [metodología y contrato](../../docs/moon/lola_methodology.md) y
[registro de variables](../../docs/moon/variables.md). Ningún resultado constituye una
evaluación de seguridad de aterrizaje.
