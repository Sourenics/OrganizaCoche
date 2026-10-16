"""Modelo de datos de Cotxà.

Vocabulario:
- Trip (trayecto): una persona, un día, hora de entrada y de salida.
- Slot (franja): (día, sentido, hora). Todas las personas que entran el
  dilluns a las 8:00 comparten la franja ("dilluns", "entrada", "8:00").
- Asignación: para cada (persona, día) un rol: conductor o pasajero.

Restricción central: el coche se queda en el centro, así que quien conduce
por la mañana conduce también por la tarde ese mismo día (y viceversa).
Por eso el rol se decide por (persona, día), no por trayecto.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

DAYS = ["dilluns", "dimarts", "dimecres", "dijous", "divendres"]


class Role(str, Enum):
    DRIVER = "conductor"
    PASSENGER = "pasajero"
    SOLO = "no_comparte"  # viene por su cuenta ese día


@dataclass(frozen=True)
class Person:
    name: str
    has_car: bool = True
    active: bool = True  # False = temporalmente fuera de la rueda (no se reparte)
    zone: str = "default"  # todos salen del mismo punto; se mantiene por si hiciera falta


@dataclass(frozen=True)
class Trip:
    person: str
    day: str
    arrival: str  # "8:00"
    departure: str  # "13:55"
    departure_flex: str | None = None  # acepta esperar hasta esta hora
    # Marca manual del organizador para ese día (None = lo decide el solver):
    #   DRIVER    "conduce": se fija como conductor/a.
    #   PASSENGER "paquete": va de pasajero/a seguro, nunca conduce ese día.
    #   SOLO      "no comparte": va por su cuenta, fuera del reparto ese día.
    fixed_role: Role | None = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.person, self.day)


@dataclass(frozen=True)
class Slot:
    day: str
    direction: str  # "entrada" | "salida"
    time: str
    zone: str = "default"


@dataclass
class Car:
    slot: Slot
    driver: str
    passengers: list[str] = field(default_factory=list)
    # Pasajeros/as que también podrían llevar este coche sin pasarse de lo que
    # les toca (como las marcas de "posible conductor" de la V6). El resto de
    # pasajeros/as son "paquetes".
    alternatives: list[str] = field(default_factory=list)

    @property
    def occupants(self) -> list[str]:
        return [self.driver, *self.passengers]


@dataclass
class Plan:
    """Resultado del reparto: rol por (persona, día) y coches por franja."""

    roles: dict[tuple[str, str], Role]
    cars: list[Car]
    capacity: int

    def driving_days(self, person: str) -> int:
        return sum(1 for (p, _), r in self.roles.items() if p == person and r is Role.DRIVER)

    def sharing_days(self, person: str) -> int:
        return sum(1 for (p, _), r in self.roles.items() if p == person and r is not Role.SOLO)
