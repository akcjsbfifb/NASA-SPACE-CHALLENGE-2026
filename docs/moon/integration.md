# Migración al backend — primera etapa

## Rama y alcance

Trabajo aislado en `feature/lunar-backend-integration`, creada desde `main`
`ff2baf39cbaa964ec1ea6657acae4dfc13eccb64`. No se integra ni modifica
`review/lunar-roughness-comparison`. Su referencia remota observada durante la
migración fue `c27b21f37f9de5a763a28b5ba93656e33c48edc9`; puede avanzar en paralelo.
No hay commit ni push de esta entrega mientras está en revisión.

La migración sólo traslada el paquete, las pruebas, configuración y documentos,
agrega un script que delega en el CLI y publica un JSON regenerado. No implementa
CSV, LEND, Diviner, iluminación, pendiente, normalización ni endpoints. No modifica
los componentes compartidos de búsqueda, frontend ni FastAPI.

## Mapa de rutas

| Antes | Después |
|---|---|
| `NASA-Lunar-Studies/src/lunar_data/` | `backend/processing/lunar_data/` |
| `NASA-Lunar-Studies/pyproject.toml` | `backend/pyproject.toml` |
| `NASA-Lunar-Studies/requirements-lock.txt` | `backend/requirements-lunar.lock.txt` |
| `NASA-Lunar-Studies/tests/` (archivos Python) | `backend/tests/lunar/` |
| `NASA-Lunar-Studies/config/sites.example.json` | `backend/tests/lunar/fixtures/sites.example.json` |
| `NASA-Lunar-Studies/config/variables.json` | `data/moon/variables.json` |
| `NASA-Lunar-Studies/docs/{variables,lola_methodology}.md` | `docs/moon/` |
| JSON publicado en `NASA-Lunar-Studies/examples/` | Se conserva; publicación nueva en `data/moon/` |
| Entradas NASA, PDF y salidas locales | Permanecen en sus ubicaciones originales |

No quedan dos archivos fuente con la misma lógica LOLA. `metadata.py`, `lola.py`,
`export.py` y `__init__.py` se trasladan sin cambiar sus bytes. El CLI añade la
resolución de rutas del checkout. El script `scripts/extract_moon.py` sólo delega.
El paquete mantiene nombre de distribución `moonstudies-lunar-data` y versión
0.1.0: la API científica no cambia y no se ha publicado una nueva versión.

## Instrucciones para el responsable de la rama de comparación

Coordinar la integración de ambas ramas después de revisar esta entrega; no
copiar el lector ni reemplazar automáticamente los archivos de otro integrante.

1. Conservar los imports existentes:

   ```python
   from lunar_data.lola import LolaRaster
   from lunar_data.metadata import MetadataError, load_metadata
   ```

2. Desde la raíz, reinstalar en el entorno que ejecuta su servicio:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r .\backend\requirements-lunar.lock.txt
   .\.venv\Scripts\python.exe -m pip install --no-deps -e .\backend
   .\.venv\Scripts\python.exe -c "import lunar_data; print(lunar_data.__file__)"
   ```

3. En su `scripts/serve_search.py`, retirar la inserción física de
   `ROOT / "NASA-Lunar-Studies" / "src"` en `sys.path`. El import se resuelve por
   el paquete instalado. No sustituirla por otro path fijo ni copiar el paquete.
4. Mantener o configurar la ruta actual de originales
   `ROOT / "NASA-Lunar-Studies" / "data" / "raw" / "lola"`: no se ha movido.
5. Actualizar referencias a registro, fixtures y documentación. Reiniciar el
   servicio para que no conserve módulos importados de la antigua ubicación.
6. Ejecutar la suite lunar y comprobar sus rutas `/moon` y `/search` en su rama.
   Esta entrega no incorpora ni prueba esos endpoints, porque no están en main.

`LolaRaster`, `load_metadata`, `MetadataError`, `sample()` y sus claves `value`,
`available`, `status`, unidades y advertencias conservan sus interfaces. El
script de ejecución y `python -m lunar_data` siguen disponibles tras reinstalar.
Los comandos que contienen la ruta anterior de instalación o pruebas requieren
actualizarse según la tabla; no se mantiene un segundo proyecto instalable.

Su `MoonSampler` abre mapas al iniciar y consulta sus píxeles durante peticiones.
Se debe coordinar después una adaptación a JSON preprocesados, manteniendo el
contrato del frontend. Un punto arbitrario no preprocesado debe distinguirse de
un dato inválido o una ausencia de cobertura. No se inventa un vecino sustituto.
La disponibilidad de rugosidad no basta para afirmar que ya fue comparada.

Su catálogo `frontend/src/data/lunarLandings.ts` y `MoonPage.tsx` no se copian.
Se deben preservar los ids compartidos y confirmar coordenadas y marco antes de
extraer nuevos sitios. El fixture actual sigue marcado como ejemplo.

En main el backend y el servidor terrestre pueden intentar usar el mismo puerto
8787, y la API terrestre sigue siendo un esqueleto incompleto. La coordinación
de ese servicio y los parámetros del comparador pertenece a sus responsables;
no se modifica aquí.

## Registro y preparación futura

La única configuración mantenida es `data/moon/variables.json`, registro 1.1.0.
Los valores LOLA, las unidades y las fuentes no cambian. Las diferencias de
metadatos intencionales respecto del registro histórico 1.0.0 son:

- Ruta de documentación actualizada.
- Pendiente seleccionada en desarrollo externo, `implemented: false`, sin valores.
- LEND seleccionado y pendiente, con dos productos separados y unidad de RATE
  aún no validada. No se implementa su estructura binaria ni se estima hielo.

El contrato de salida sigue siendo 1.0.0. Los consumidores deben admitir claves
de variables adicionales. La condición externa de desarrollo se consulta en
el registro; el procesador sigue informando `not_implemented` para la pendiente.
Diviner e iluminación permanecen pendientes. Mineralogía, disponibilidad de
agua/hielo y seguridad integral permanecen excluidas. La falta de datos nunca
significa condiciones favorables.

CSV, los perfiles de normalización y los lectores futuros no tienen módulos
vacíos ni implementaciones anticipadas. Se añadirán al paquete único cuando
se autoricen. El buscador terrestre mantiene Parquet y todas sus fórmulas.

## Verificación antes y después

Antes de mover archivos se ejecutan los 60 casos y se genera
`NASA-Lunar-Studies/output/backend_migration.before.json`. Un manifiesto local
registra hashes y tamaños de 17 archivos: 15 originales NASA, el PDF y el JSON
histórico. No se suben esas entradas ni sus copias al paquete.

Después de instalar desde backend se repiten los 60 casos, incluida una
extracción real y el script desde otro directorio. La comparación contra la
referencia exige igualdad exacta de los registros completos de elevación y
rugosidad (raw, convertido, unidades, estados, centros y píxeles), coordenadas,
referencia espacial y fuentes con hashes. Se registran por separado las
diferencias intencionales de variables pendientes y configuración.

| Ejemplo | Magnitud | Raw | Convertido (m) | Fila, columna |
|---|---|---:|---:|---|
| 0°, 0° E | Elevación | −0.7186850309371948 km | −718.6850309371948 | 1440, 0 |
| 0°, 0° E | Rugosidad | 0.4296111762523651 m | 0.4296111762523651 | 2880, 0 |
| −85°, −10° E | Elevación | −0.3510236144065857 km | −351.0236144065857 | 2800, 5600 |
| −85°, −10° E | Rugosidad | 0.3567740023136139 m | 0.3567740023136139 | 5600, 11200 |

El JSON histórico conserva SHA-256
`9ed1e45c8af2b975e14fdfaeb72685d074ef1a060a09f4bda38ed7e1da8ec570`.
El JSON nuevo tendrá otros hashes de código y registro; no se exige igualdad
del documento completo. Dos ejecuciones nuevas con iguales entradas sí deben
ser idénticas. La cantidad de decimales no representa incertidumbre física.

La evidencia detallada de esta ejecución queda local en
`NASA-Lunar-Studies/output/backend_migration.validation.json`. Estos son
controles internos de lectura e integridad local. QGIS/GDAL y la comparación
con checksums oficiales NASA siguen pendientes; no se afirma validación externa.

## Empaquetado y archivos ignorados

Setuptools descubre sólo `lunar_data*` bajo `backend/processing/`; no incorpora
datasets, modelos, servicios FastAPI ni el catálogo del frontend al paquete.
Las reglas de Git conservan entradas y PDF fuera del índice. Los `.dockerignore`
de raíz y backend excluyen entradas y artefactos locales de esos contextos.
No se creó ni ejecutó un despliegue; un contexto diferente necesita revisar sus
propias reglas antes de publicar una imagen.
