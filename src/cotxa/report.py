"""Salida legible del plan: tabla semanal y resumen de equidad."""
from __future__ import annotations

import csv
import io

from .models import DAYS, Plan, Role


def weekly_table(plan: Plan) -> str:
    out: list[str] = []
    for day in DAYS:
        day_cars = [c for c in plan.cars if c.slot.day == day]
        if not day_cars:
            continue
        out.append(f"\n== {day.upper()} ==")
        for direction in ("entrada", "salida"):
            cars = sorted(
                (c for c in day_cars if c.slot.direction == direction),
                key=lambda c: (_minutes(c.slot.time), c.driver),
            )
            out.append(f"  {direction.capitalize()}:")
            for c in cars:
                pax = ", ".join(c.passengers) if c.passengers else "(solo)"
                zone = f" [{c.slot.zone}]" if c.slot.zone != "default" else ""
                alt = f"  (también podrían: {', '.join(c.alternatives)})" if c.alternatives else ""
                out.append(f"    {c.slot.time:>5}{zone}  🚗 {c.driver:<10} → {pax}{alt}")
    return "\n".join(out)


def fairness_summary(plan: Plan) -> str:
    people = sorted({p for p, _ in plan.roles})
    rows = []
    for p in people:
        d, s = plan.driving_days(p), plan.sharing_days(p)
        pct = f"{100 * d / s:5.0f}%" if s else "   -"
        rows.append(f"  {p:<10} conduce {d}/{s} días  {pct}")
    return "\nEquidad (días conduciendo / días compartiendo):\n" + "\n".join(rows)


def roles_csv(plan: Plan) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["persona", "dia", "rol"])
    for (p, day), r in sorted(plan.roles.items(), key=lambda kv: (kv[0][0], DAYS.index(kv[0][1]))):
        w.writerow([p, day, r.value])
    return buf.getvalue()


def _minutes(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)
