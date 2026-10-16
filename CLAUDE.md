# CLAUDE.md — contexto para Claude Code

## Qué es esto
Cotxà reparte coche compartido entre ~17 profesores/as con horarios distintos
cada día. Objetivo: cubrir todas las franjas de entrada/salida con el mínimo
de coches y repartir la carga de conducir de forma equitativa.

## Reglas del dominio (no romper)
- **Quien conduce por la mañana conduce por la tarde el mismo día.** El rol es
  por `(persona, día)`. Nunca asignar roles distintos a la ida y a la vuelta.
- Una franja es `(día, sentido, hora, zona)`. Sólo se comparte dentro de la
  misma zona.
- Todo el mundo participa en la rueda y tiene coche. `active: false` en
  `config.json` ⇒ fuera temporalmente (no se reparte, pero sus horarios se
  conservan). `no_comparte` ⇒ no entra en el reparto ese día concreto.
- Todos salen del mismo punto de encuentro: una sola zona (`zone` existe pero
  no se usa salvo que cambie la situación).
- Capacidad 4 por defecto (a veces 5: `--capacity 5`).
- `salida_flex`: la persona acepta salir más tarde si así va acompañada.
- Equidad = igualar `días conduciendo / días compartiendo` entre personas.
  Alguien que viene 2 días no debe conducir tanto como quien viene 5.

## Privacidad (regla dura)
- Los nombres y horarios reales del claustro **nunca** entran en el repositorio
  ni en `docs/index.html`. `data/horaris.sample.csv` tiene nombres inventados;
  `data/horaris.csv` (real) está en `.gitignore`. No lo añadas, no lo copies a
  tests, no lo incrustes en la web. `test_no_real_data_in_repo` lo vigila.
- El administrador maneja los datos reales como JSON importado/exportado en la
  app (vive en su navegador).

## App web (docs/)
- `web/index.template.html` es la fuente; `scripts/build_web.py` incrusta los
  datos iniciales y escribe `docs/index.html`, que sirve GitHub Pages.
  **Edita siempre la plantilla, nunca `docs/index.html` a mano.**
- HTML + CSS + JS vanilla en un solo archivo, sin build. Única dependencia:
  SheetJS (`docs/vendor/xlsx.full.min.js`, 0.18.5, licencia Apache-2.0) para
  exportar Excel. El PDF se hace con `window.print()` + CSS `@media print`.
- La función `solve(state)` del JS es un port 1:1 de `solver.py`. Cualquier
  cambio en el algoritmo se hace en los dos sitios.
- Estado en `localStorage` (clave `cotxa.state.v1`) + exportar/importar JSON.
  Formato: `{capacity, people:[{name, active, days:{dilluns:{in,out,flex,share}}}]}`.

## Código
- Python ≥ 3.11, sin dependencias en runtime (openpyxl sólo para importar).
- `src/cotxa/models.py` dataclasses · `solver.py` algoritmo · `report.py`
  salida · `cli.py` entrada · `io.py` carga de CSV/JSON.
- `solve(trips, people, capacity) -> SolveResult(plan, warnings)` es la API
  interna; cualquier solver nuevo debe respetar esa firma para poder compararlos.
- Tests con `pytest` (`tests/`). `test_real_data_is_balanced` corre sobre los
  datos de ejemplo de `data/horaris.sample.csv`; añade un test por cada regla nueva.
- Idioma: identificadores en inglés, docstrings/comentarios/mensajes al usuario
  en castellano. Nombres de días en valenciano (`dilluns`…`divendres`) porque
  así vienen en los datos.

## Comandos
```bash
pip install -e ".[dev,import]"
pytest
cotxa plan data/horaris.sample.csv
python scripts/build_web.py                      # regenera docs/ con datos de ejemplo
python scripts/import_xlsx.py "Cotxà V6.xlsx" data/horaris.csv   # real, queda fuera de git
```

## Datos de origen
`Cotxà V6.xlsx`: rejilla manual. Símbolos: `=` conductor, `○` pasajero
("paquet"), `.` no comparte, `→` espera a la siguiente marca. Varias columnas
con la misma hora = varios coches. `scripts/import_xlsx.py` la convierte en CSV.

## Confirmado con el usuario
Capacidad 4 (a veces 5). Mismo punto de encuentro para todos. Todos participan
salvo ausencias temporales (`active: false`). Ver README > Hoja de ruta.
