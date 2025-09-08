# notebooks/

Sección para análisis exploratorio, pruebas y demostraciones en Jupyter.

## Convenciones
- Nombres: `NNN-tema.ipynb` (p. ej. `001-exploracion.ipynb`).
- Kernel: Python 3.x (mismo entorno que los scripts).
- Rutas: no usar rutas absolutas. Detecta la raíz del repo y escribe en `outputs/`.
- Datos: leer de `Corpus/` (solo lectura). No modificar datos crudos.
- Salidas: guardar derivados en `outputs/processed/` y figuras/reportes en `outputs/reports/`.
- Ligereza: evita incrustar grandes tablas/figuras en el notebook; guarda a archivos en `outputs/` y enlaza.

## Snippet de rutas (recomendado)
```python
from pathlib import Path

# Detecta la raíz del repo (carpeta que contiene `outputs/` o `.git`)
REPO = Path.cwd().resolve()
while REPO.parent != REPO and not (REPO / 'outputs').exists() and not (REPO / '.git').exists():
    REPO = REPO.parent

OUTPUTS = REPO / 'outputs'
PROCESSED = OUTPUTS / 'processed'
REPORTS = OUTPUTS / 'reports'
PROCESSED.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)
print('Repo root:', REPO)
```

## Buenas prácticas
- Versiona notebooks limpios (Kernel apagado, sin resultados pesados).
- Para procesos largos, prefiere scripts en `scripts/` e invócalos desde el notebook.
- Documenta supuestos, versión de datos y parámetros al inicio del notebook.

## Plantillas
Coloca plantillas reutilizables en `notebooks/templates/`.
