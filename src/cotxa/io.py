"""Carga de datos: horarios (CSV) y configuración de personas (JSON)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .models import DAYS, Person, Role, Trip

# Columna opcional "marca" del CSV: marca manual del organizador para ese día.
MARKS = {"conduce": Role.DRIVER, "paquete": Role.PASSENGER, "no_comparte": Role.SOLO}


def load_trips(path: str | Path) -> list[Trip]:
    trips: list[Trip] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["dia"] not in DAYS:
                raise ValueError(f"Día desconocido: {row['dia']!r}")
            fixed = None
            # Del histórico V6 sólo respetamos "no_comparte"; conductor/pasajero los decide el solver
            if Role.SOLO.value in (row.get("rol_entrada_v6"), row.get("rol_salida_v6")):
                fixed = Role.SOLO
            # La columna "marca" (conduce / paquete / no_comparte) manda sobre el histórico
            mark = (row.get("marca") or "").strip().lower()
            if mark:
                if mark not in MARKS:
                    raise ValueError(f"Marca desconocida: {mark!r} (usa conduce, paquete o no_comparte)")
                fixed = MARKS[mark]
            trips.append(
                Trip(
                    person=row["persona"].strip(),
                    day=row["dia"],
                    arrival=row["entrada"],
                    departure=row["salida"],
                    departure_flex=row.get("salida_flex") or None,
                    fixed_role=fixed,
                    arrival_flex=row.get("entrada_flex") or None,
                )
            )
    return trips


def load_people(path: str | Path | None, trips: list[Trip]) -> dict[str, Person]:
    """Lee people.json si existe; cualquier persona sin entrada recibe valores por defecto."""
    people: dict[str, Person] = {}
    if path and Path(path).exists():
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for name, cfg in data.get("people", {}).items():
            people[name] = Person(
                name,
                has_car=cfg.get("has_car", True),
                active=cfg.get("active", True),
                zone=cfg.get("zone", "default"),
                max_drive=cfg.get("max_drive"),
            )
    for t in trips:
        people.setdefault(t.person, Person(t.person))
    return people


def load_config(path: str | Path | None) -> dict:
    if path and Path(path).exists():
        return json.loads(Path(path).read_text(encoding="utf-8"))
    return {}
