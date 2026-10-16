"""Importa la rejilla manual (Cotxà V6.xlsx) a data/horaris.csv.

La hoja tiene, por cada día, un bloque de columnas de *Entrades* y otro de
*Eixides*. Los bloques están separados por una columna vacía en la fila de horas.
Cada persona tiene una marca por bloque:
    '='  conductor/a      '○'  pasajero/a ("paquet")
    '.'  no comparte ese trayecto      '→'  espera hasta la siguiente marca
Varias columnas con la misma hora = varios coches a esa hora.

Uso:  python scripts/import_xlsx.py "Cotxà V6.xlsx" data/horaris.csv
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import openpyxl

ROLE = {"=": "conductor", "○": "pasajero", ".": "no_comparte", "→": "espera"}
DAYS = ["dilluns", "dimarts", "dimecres", "dijous", "divendres"]


def blocks(time_row: list) -> list[list[int]]:
    """Índices de columna agrupados en bloques contiguos con hora."""
    out, cur = [], []
    for i, t in enumerate(time_row):
        if i == 0:
            continue
        if t is None:
            if cur:
                out.append(cur)
                cur = []
        else:
            cur.append(i)
    if cur:
        out.append(cur)
    return out


def norm_time(t) -> str:
    return str(t).replace(".", ":").strip()


def main(src: str, dst: str) -> None:
    ws = openpyxl.load_workbook(src, data_only=True).worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True) if any(c is not None for c in r)]
    # Fila de horas: la primera que contiene '8.00' en alguna celda
    ti = next(i for i, r in enumerate(rows) if any(str(c).startswith("8.") for c in r if c))
    time_row = rows[ti]
    rows = rows[: ti + 1] + [r for r in rows[ti + 1 :] if r[0]]  # solo filas de personas
    bl = blocks(time_row)
    assert len(bl) == 10, f"Esperaba 10 bloques (5 días x entrada/salida), hay {len(bl)}"

    records = []
    for r in rows[ti + 1 :]:
        name = r[0]
        if not name:
            continue
        for d, day in enumerate(DAYS):
            entry = {time_row[i]: r[i] for i in bl[2 * d] if r[i] is not None}
            exit_ = {time_row[i]: r[i] for i in bl[2 * d + 1] if r[i] is not None}
            if not entry and not exit_:
                continue  # no viene ese día
            rec = {"persona": name, "dia": day}
            # Entrada: una sola marca normalmente
            if entry:
                t, mark = next(iter(entry.items()))
                rec["entrada"], rec["rol_entrada_v6"] = norm_time(t), ROLE.get(mark, mark)
            # Salida: la hora real es la primera marca; '→' indica que espera a la siguiente
            if exit_:
                items = list(exit_.items())
                t, mark = items[0]
                rec["salida"], rec["rol_salida_v6"] = norm_time(t), ROLE.get(mark, mark)
                if mark == "→" and len(items) > 1:
                    rec["salida_flex"] = norm_time(items[1][0])
                    rec["rol_salida_v6"] = ROLE.get(items[1][1], items[1][1])
            records.append(rec)

    fields = ["persona", "dia", "entrada", "salida", "salida_flex", "rol_entrada_v6", "rol_salida_v6"]
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(records)
    print(f"{len(records)} filas -> {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "data/horaris.csv")
