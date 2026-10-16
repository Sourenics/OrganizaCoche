"""Cotxà: reparto equilibrado de coche compartido entre profesorado."""
from .models import Car, Person, Plan, Role, Slot, Trip  # noqa: F401
from .solver import solve  # noqa: F401
