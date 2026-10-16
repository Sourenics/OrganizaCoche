# Cotxà 🚗

Reparto equilibrado de coche compartido para un claustro en el que cada
persona entra y sale a una hora distinta cada día.

Parte de la hoja manual *Cotxà V6* y la convierte en datos + un algoritmo que
decide **quién conduce cada día** de forma justa, y **quién va con quién** en
cada franja horaria.

## Privacidad: qué hay en el repositorio y qué no

**Nada de lo que se publica contiene datos reales.** `data/horaris.sample.csv`
y la página `docs/index.html` usan nombres inventados. Los horarios reales del
claustro los guarda el administrador en un JSON **fuera del repositorio**
(`.gitignore` bloquea `data/horaris.csv` y `*.dades-reals.json`) y los carga
en la app con *Importar JSON*; se quedan en su navegador. Tras cada cambio,
*Exportar JSON* y guardar el archivo en un sitio privado (Drive, el móvil…).

Ten en cuenta que una página de GitHub Pages es pública aunque el repositorio
sea privado, y que en el plan gratuito Pages sólo funciona con repositorios
públicos. Por eso la separación anterior es la que protege los datos, no la
visibilidad del repositorio.

## La app (GitHub Pages)

`docs/index.html` es una aplicación para **el organizador**, de una sola
página y sin servidor: tabla editable de personas y horarios (o *Empezar de
cero*), botón *Calcular reparto*, vista semanal, reparto por día y franja,
tabla de equidad, y exportación a **Excel** (4 hojas: Semana, Coches, Equidad,
Horarios) y a **PDF** (botón *Guardar PDF / Imprimir* → "Guardar como PDF").
Cada persona y día lleva una **marca**: *Auto* (decide la app), *Conduce*
(se fija como conductor/a), *Paquete* (va de pasajero/a seguro) o *No
comparte*. En el reparto, cada coche indica quién más **también podría**
llevarlo sin pasarse de lo que le toca, como en la V6; un clic en la vista
semanal alterna Auto → Conduce → Paquete y recalcula. Las fechas del
**ciclo** (periodo en que se repite el reparto, normalmente un trimestre) se
indican en Horarios y salen en el rótulo, el PDF y el Excel. Al acabar,
**Cerrar ciclo** guarda su resumen en un historial (en tu JSON): la tabla de
equidad muestra el **saldo** acumulado de cada persona (días conducidos de
más o de menos respecto a lo que le tocaba) y la app lo compensa al calcular
el ciclo siguiente; las marcas manuales mandan sobre esa compensación.
La vista **Rejilla** reproduce la disposición de la V6 (personas en filas, un
coche por columna como barra de color, ● conduce · ◐ también podría · ○
paquete) y es lo que sale en el PDF, en apaisado; el interruptor *PDF con
detalle por día* añade una segunda hoja con la semana, los coches y la equidad.
El interruptor **Topes de días** añade una columna *Máx./sem.* para limitar,
si se quiere, los días que conduce cada persona a la semana (la app sólo lo
supera si no hay otra forma de cubrir una franja, y avisa).
La librería de Excel (SheetJS) va incluida en `docs/vendor/`, así que la app
funciona sin conexión y sin depender de terceros.
Los datos se guardan en el navegador y se pueden **exportar/importar** en JSON
(haz una exportación tras cada cambio importante: es tu copia de seguridad).

Publicarla (una sola vez):

1. Sube el repositorio a GitHub.
2. En el repositorio: **Settings → Pages → Build and deployment → Source:
   Deploy from a branch → Branch: `main`, carpeta `/docs` → Save**.
3. En un minuto estará en `https://<usuario>.github.io/<repositorio>/`.
   Desde el móvil, "Añadir a pantalla de inicio" la deja como una app.

`python scripts/build_web.py` regenera la página con los datos de ejemplo.
`--data data/horaris.csv` incrusta datos reales **sólo para uso local**: no
publiques ese `docs/index.html`.
El solver en JavaScript es un port de `src/cotxa/solver.py` y da el mismo
resultado; si cambias el algoritmo, cambia los dos (o haz que el test de
paridad lo detecte, ver hoja de ruta).

## Cómo funciona

1. **Datos** (`data/horaris.sample.csv`, o tu `data/horaris.csv` local): una fila por persona y día con hora de
   entrada y de salida. Opcionalmente `entrada_flex` / `salida_flex` (horas
   flexibles: la app mueve a la persona sólo si así no va sola o se ahorra un
   coche) y el rol histórico de la V6 (sólo se respeta `no_comparte`).
2. **Franjas**: todas las personas que entran el dilluns a las 8:00 forman la
   franja `(dilluns, entrada, 8:00)`. Cada franja necesita `ceil(n / plazas)`
   coches.
3. **Restricción central**: el coche se queda en el centro, así que **quien
   conduce por la mañana conduce también a la vuelta**. El rol se decide por
   `(persona, día)`, no por trayecto. Esto es lo que hace el puzzle difícil:
   el conductor de las 8:00 tiene que servir también a la gente que sale a su
   misma hora de salida.
4. **Solver** (`src/cotxa/solver.py`): greedy de cobertura + búsqueda local
   que minimiza la desigualdad de `días conduciendo / días compartiendo`.
5. **Informe**: tabla semanal por día y franja, resumen de equidad, avisos
   (franjas sin conductor posible, gente que no cabe).

## Uso

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,import]"

cotxa plan data/horaris.sample.csv          # imprime el reparto (datos de ejemplo)
cotxa plan data/horaris.csv --capacity 5    # con tus datos locales, 5 plazas
cotxa plan data/horaris.csv --csv out/roles.csv

# Volver a importar desde la hoja de cálculo
python scripts/import_xlsx.py "Cotxà V6.xlsx" data/horaris.csv

pytest
```

`data/config.json` fija la capacidad (4 por defecto; a veces caben 5) y
permite sacar temporalmente a alguien de la rueda con `"active": false`, sin
borrar sus horarios, o ponerle un tope de días conduciendo a la semana con
`"max_drive": 2`. Todo el mundo sale del mismo punto de encuentro.

## Formato de `data/horaris.csv`

| columna | ejemplo | notas |
|---|---|---|
| persona | `Aina` | |
| dia | `dilluns` | `dilluns`…`divendres` |
| entrada | `8:00` | |
| salida | `13:55` | |
| entrada_flex | `8:00` | opcional: acepta entrar antes, desde esta hora, si así va acompañada o se ahorra un coche |
| salida_flex | `13:55` | opcional: acepta esperar hasta esta hora, con la misma regla |
| marca | `paquete` | opcional: `conduce` (se fija como conductor/a), `paquete` (nunca conduce ese día) o `no_comparte` |
| rol_entrada_v6 / rol_salida_v6 | `conductor` | histórico de la hoja; sólo `no_comparte` afecta al solver |

## Estructura

```
data/            horaris.sample.csv (nombres inventados), config.json · horaris.csv real: ignorado por git
docs/            index.html — la app publicada en GitHub Pages (generada)
web/             index.template.html — plantilla de la app (edita ésta)
scripts/         import_xlsx.py — lee la rejilla manual · build_web.py — genera docs/
src/cotxa/       models.py · io.py · solver.py · report.py · cli.py
tests/           pytest
```

## Hoja de ruta (ideas, por orden sugerido)

- [ ] **Entender la V6**: hay franjas con 3 conductores para 4 personas
      (p. ej. dilluns 8:00). Como todos salen del mismo sitio, probablemente
      son preferencias o restricciones no escritas que el CSV aún no recoge.
- [ ] **Preferencias y restricciones blandas**: pares que prefieren (o no)
      ir juntos, máximo de días conduciendo por persona, "este día tengo que
      llevar el coche sí o sí".
- [ ] **Rotación entre semanas**: generar planes A/B (semanas pares/impares)
      para que la equidad se mida en el trimestre y no sólo en la semana.
- [ ] **Solver exacto**: formular como ILP/CP-SAT (OR-Tools) — ~85 variables
      binarias — y comparar con el greedy. La función `solve()` ya devuelve un
      `Plan`, así que es sustituible.
- [ ] **Compensación económica**: contar km/viajes por persona y proponer
      ajustes.
- [ ] **Test de paridad** Python ↔ JavaScript (ejecutar el solver JS con
      Node o Playwright y comparar roles) para que no se desincronicen.
- [ ] **Datos compartidos**: hoy el administrador es la única fuente de
      verdad (JSON exportado). Si hiciera falta que varias personas editen,
      añadir un almacén gratuito (Firebase/Supabase) sin rehacer la página.
- [ ] **Exportar a xlsx** con el mismo aspecto que la V6.
- [ ] **Imprevistos**: "hoy Biel no viene" → recalcular sólo ese día
      minimizando cambios.
