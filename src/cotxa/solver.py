"""Reparto equilibrado de coches.

Enfoque (v0, sin dependencias):
1. Agrupar trayectos en franjas (día, sentido, hora, zona).
2. Cada franja necesita ceil(n / capacidad) coches.
3. Elegir por (persona, día) quién conduce, de forma que todas las franjas
   queden cubiertas y la carga de conducción sea lo más pareja posible.
   Las marcas manuales (conduce / paquete) se respetan siempre: un "conduce"
   se fija como conductor y un "paquete" nunca conduce ese día.
   `bias` (opcional) es la compensación de ciclos anteriores, en días de
   conducir a la semana: se suma a los días conduciendo de cada persona al
   medir la carga, así que quien condujo de más antes conduce menos ahora.
   - Greedy: cubrir primero la franja con mayor déficit, eligiendo a la
     persona con menor ratio (días conduciendo / días compartiendo).
   - Búsqueda local: intercambios conductor<->pasajero dentro del mismo día
     que mantienen la cobertura y reducen la desigualdad.
4. Repartir pasajeros entre los coches de cada franja y, en cada coche,
   señalar quién más podría llevarlo sin pasarse de lo que le toca
   ("también podrían"); el resto son "paquetes", como en la V6.

Es un problema de cobertura pequeño (~17 personas x 5 días); si el greedy se
queda corto, el siguiente paso natural es formularlo como ILP/CP-SAT
(ver README > Hoja de ruta).
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from .models import Car, Person, Plan, Role, Slot, Trip


@dataclass
class SolveResult:
    plan: Plan
    warnings: list[str] = field(default_factory=list)


def _slots_for(trip: Trip, zone: str) -> tuple[Slot, Slot]:
    return (
        Slot(trip.day, "entrada", trip.arrival, zone),
        Slot(trip.day, "salida", trip.departure, zone),
    )


def _apply_flex(trips: list[Trip], people: dict[str, Person]) -> list[Trip]:
    """Si alguien saldría solo pero acepta esperar, lo movemos a la hora flexible
    cuando allí sí hay compañía."""
    counts: dict[tuple, int] = defaultdict(int)
    for t in trips:
        if t.fixed_role is Role.SOLO or not people[t.person].active:
            continue
        counts[(t.day, t.departure, people[t.person].zone)] += 1
    out = []
    for t in trips:
        z = people[t.person].zone
        if (
            t.departure_flex
            and t.fixed_role is not Role.SOLO
            and counts[(t.day, t.departure, z)] == 1
            and counts[(t.day, t.departure_flex, z)] >= 1
        ):
            t = Trip(t.person, t.day, t.arrival, t.departure_flex, None, t.fixed_role)
        out.append(t)
    return out


def _fairness(driving: dict[str, float], sharing: dict[str, int]) -> float:
    ratios = [driving[p] / sharing[p] for p in sharing if sharing[p]]
    if not ratios:
        return 0.0
    mean = sum(ratios) / len(ratios)
    return sum((r - mean) ** 2 for r in ratios)


def solve(
    trips: list[Trip], people: dict[str, Person], capacity: int = 4,
    bias: dict[str, float] | None = None,
) -> SolveResult:
    warnings: list[str] = []
    trips = _apply_flex(trips, people)
    bias = bias or {}

    roles: dict[tuple[str, str], Role] = {}
    locked: set[tuple[str, str]] = set()  # marcas manuales: el solver no las toca
    members: dict[Slot, list[str]] = defaultdict(list)
    person_slots: dict[tuple[str, str], tuple[Slot, Slot]] = {}
    sharing: dict[str, int] = defaultdict(int)
    driving: dict[str, int] = defaultdict(int)
    pax_days: dict[str, int] = defaultdict(int)  # días marcados "paquete" por persona
    # carga = días conduciendo + compensación de ciclos anteriores; es lo que se iguala
    load: dict[str, float] = {}

    def _load() -> dict[str, float]:
        for p in sharing:
            load[p] = driving[p] + bias.get(p, 0.0)
        return load

    for t in trips:
        if not people[t.person].active:
            continue  # fuera de la rueda temporalmente: ni conduce ni ocupa plaza
        if t.fixed_role is Role.SOLO:
            roles[t.key] = Role.SOLO
            continue
        roles[t.key] = Role.PASSENGER
        sharing[t.person] += 1
        driving.setdefault(t.person, 0)
        if t.fixed_role is Role.DRIVER:
            if people[t.person].has_car:
                roles[t.key] = Role.DRIVER
                driving[t.person] += 1
                locked.add(t.key)
            else:
                warnings.append(f"{t.person}, {t.day}: marcado 'conduce' pero no tiene coche; se ignora la marca")
        elif t.fixed_role is Role.PASSENGER:
            locked.add(t.key)
            pax_days[t.person] += 1
        s_in, s_out = _slots_for(t, people[t.person].zone)
        members[s_in].append(t.person)
        members[s_out].append(t.person)
        person_slots[t.key] = (s_in, s_out)

    for p, n in pax_days.items():
        if n == sharing[p]:
            warnings.append(f"{p}: marcado 'paquete' todos sus días; no conducirá nunca")

    required = {s: math.ceil(len(m) / capacity) for s, m in members.items()}

    def drivers_in(slot: Slot) -> int:
        return sum(1 for p in members[slot] if roles[(p, slot.day)] is Role.DRIVER)

    def deficit(slot: Slot) -> int:
        return required[slot] - drivers_in(slot)

    def feasible() -> bool:
        return all(deficit(s) <= 0 for s in members)

    # --- 1. Greedy de cobertura -------------------------------------------------
    while True:
        slot = max(members, key=deficit)
        if deficit(slot) <= 0:
            break
        candidates = [
            p for p in members[slot]
            if roles[(p, slot.day)] is Role.PASSENGER and people[p].has_car
            and (p, slot.day) not in locked
        ]
        if not candidates:
            warnings.append(
                f"{slot.day} {slot.direction} {slot.time}: faltan conductores "
                f"({drivers_in(slot)} coches para {len(members[slot])} personas)"
            )
            required[slot] = drivers_in(slot)  # aceptamos el déficit y seguimos
            continue

        def score(p: str) -> tuple:
            other = [s for s in person_slots[(p, slot.day)] if s != slot][0]
            return (
                (driving[p] + bias.get(p, 0.0)) / sharing[p],  # menos carga primero
                -max(deficit(other), 0),        # que ayude también en su otra franja
                p,
            )

        best = min(candidates, key=score)
        roles[(best, slot.day)] = Role.DRIVER
        driving[best] += 1

    # --- 2. Búsqueda local: quitar sobrantes e intercambiar -----------------------
    improved = True
    while improved:
        improved = False
        base = _fairness(_load(), sharing)
        for (p, day), r in list(roles.items()):
            if r is not Role.DRIVER or (p, day) in locked:
                continue
            # a) ¿sobra este conductor?
            roles[(p, day)] = Role.PASSENGER
            driving[p] -= 1
            if feasible() and _fairness(_load(), sharing) <= base:
                improved = True
                break
            # b) intercambio con un pasajero del mismo día con coche
            swapped = False
            # dict.fromkeys en vez de set: orden determinista (igual que el Set de JS)
            for q in dict.fromkeys(m for s in person_slots[(p, day)] for m in members[s]):
                if q == p or roles[(q, day)] is not Role.PASSENGER or not people[q].has_car or (q, day) in locked:
                    continue
                roles[(q, day)] = Role.DRIVER
                driving[q] += 1
                if feasible() and _fairness(_load(), sharing) < base - 1e-9:
                    swapped = improved = True
                    break
                roles[(q, day)] = Role.PASSENGER
                driving[q] -= 1
            if swapped:
                break
            roles[(p, day)] = Role.DRIVER
            driving[p] += 1

    # --- 3. Formar coches por franja ---------------------------------------------
    ratios = [_load()[p] / sharing[p] for p in sharing if sharing[p]]
    mean_ratio = sum(ratios) / len(ratios) if ratios else 0.0

    def could_drive(q: str, p: str, day: str) -> bool:
        """¿Podría q llevar el coche en lugar de p? Sí, si aún no llega a lo que le toca."""
        if (q, day) in locked or not people[q].has_car:
            return False
        if load[q] >= mean_ratio * sharing[q] - 1e-9:
            return False
        roles[(p, day)], roles[(q, day)] = Role.PASSENGER, Role.DRIVER
        ok = feasible()
        roles[(p, day)], roles[(q, day)] = Role.DRIVER, Role.PASSENGER
        return ok

    cars: list[Car] = []
    for slot in sorted(members, key=lambda s: (s.day, s.direction, s.time, s.zone)):
        drivers = sorted(p for p in members[slot] if roles[(p, slot.day)] is Role.DRIVER)
        passengers = sorted(p for p in members[slot] if roles[(p, slot.day)] is Role.PASSENGER)
        slot_cars = [Car(slot, d) for d in drivers]
        if not slot_cars:
            warnings.append(f"{slot.day} {slot.direction} {slot.time}: nadie puede conducir")
            continue
        for i, p in enumerate(passengers):
            car = slot_cars[i % len(slot_cars)]
            if len(car.occupants) >= capacity:
                warnings.append(f"{slot.day} {slot.direction} {slot.time}: {p} no cabe")
            car.passengers.append(p)
        for car in slot_cars:
            car.alternatives = [q for q in car.passengers if could_drive(q, car.driver, slot.day)]
        cars.extend(slot_cars)

    return SolveResult(Plan(roles, cars, capacity), warnings)
