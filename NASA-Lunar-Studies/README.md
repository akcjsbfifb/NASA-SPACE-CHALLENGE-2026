# Entradas locales y publicación histórica

El único procesador lunar ahora está en
[`backend/processing/lunar_data/`](../backend/processing/lunar_data/).
Las [instrucciones actuales](../docs/moon/README.md) describen instalación,
extracción y pruebas desde la raíz del repositorio.

Esta carpeta conserva `data/raw/`, los resultados locales de `output/`, el PDF
de planificación y el JSON histórico de `examples/`. No se eliminaron ni movieron
las entradas científicas. No se mantiene otra implementación del lector aquí.

Los datos compartidos mantenidos están en [`data/moon/`](../data/moon/).
La migración y la compatibilidad con la rama del compañero se documentan en
[`docs/moon/integration.md`](../docs/moon/integration.md).
