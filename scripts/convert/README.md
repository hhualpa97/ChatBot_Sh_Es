# scripts/convert/

Herramientas de conversión y preparación de datos.

## `html_to_txt.py`
Conversor de HTML a TXT con modos de salida flexibles y utilidades de limpieza.

- Entrada: directorio con `.htm`/`.html` (ajustable con `--ext`, p. ej. `--ext htm,html,xhtml`).
- Salida por defecto: `outputs/processed/<dataset>_txt/` (detecta la raíz del repo).

Modos de salida
- Per-archivo (por defecto): genera un `.txt` por fuente.
- `--single-file <ruta>`: además genera un único consolidado con todo el contenido.
- `--single-only`: genera solo un consolidado (no crea `.txt` por archivo). Si no das `--single-file`, usa `<output_dir>/all.txt`.
- `--merge-only`: no reconvierte; une los `.txt` existentes bajo `<output_dir>` en un único archivo (requiere `--single-file` o usa `<output_dir>/all.txt`).

Opciones de limpieza y formato
- `--strip-leading-numbers`: quita números tipo versículo al inicio de línea (1–4 dígitos, opcional `.` o `)`), conservador para no alterar texto interno.
- `--merge-strip-leading-numbers`: aplica la limpieza anterior al consolidar (merge/single-only).
- `--strip-angle-buttons`: elimina tokens de navegación como `<`, `>`, `<<`, `>>`, «», ‹›.
- `--no-section-headers`: en consolidado, omite encabezados `===== <archivo> =====` por cada fuente.
- `--include-urls`: añade `(URL)` tras el texto de enlaces en la conversión.

Entrada y descubrimiento de archivos
- `--recursive`: busca recursivamente.
- `--ext`: extensiones a considerar (por defecto: `htm,html`).
- `--encoding`: encoding fuente (por defecto: `utf-8`, se tolera `errors="replace"`).

Destino de salida
- `-o/--output-dir`: ruta explícita para salidas.
- `--dest-scope {outputs,sibling}`: cuando no se da `-o`, controla el destino por defecto:
  - `outputs`: `<repo>/outputs/processed/<dataset>_txt/` (recomendado).
  - `sibling`: `../<dataset>_txt` junto al directorio de entrada (modo legado).

Ejemplos
- Per-archivo a `outputs/`:
  `python3 scripts/convert/html_to_txt.py -i Corpus/shpNTpo_html --dest-scope outputs`
- Solo consolidado limpio (flujo recomendado para el modelo):
  `python3 scripts/convert/html_to_txt.py -i Corpus/shpNTpo_html --single-only --strip-leading-numbers --no-section-headers`
- Generar `.txt` por archivo y además un consolidado:
  `python3 scripts/convert/html_to_txt.py -i Corpus/shpNTpo_html --single-file outputs/processed/shpNTpo_txt/all.txt`
- Unir lo ya convertido aplicando limpieza:
  `python3 scripts/convert/html_to_txt.py -i Corpus/shpNTpo_html --merge-only --merge-strip-leading-numbers --single-file outputs/processed/shpNTpo_txt/all.txt`
