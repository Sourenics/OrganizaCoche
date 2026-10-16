"""CLI: `cotxa plan data/horaris.csv`"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .io import load_config, load_people, load_trips
from .report import fairness_summary, roles_csv, weekly_table
from .solver import solve


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="cotxa", description="Reparto de coche compartido")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="Calcula el reparto semanal")
    p.add_argument("horaris", help="CSV de horarios (ver data/horaris.csv)")
    p.add_argument("--config", default="data/config.json", help="JSON con capacidad y personas")
    p.add_argument("--capacity", type=int, help="Plazas por coche (incluido conductor)")
    p.add_argument("--csv", help="Guarda los roles por (persona, día) en este CSV")
    args = ap.parse_args(argv)

    trips = load_trips(args.horaris)
    cfg = load_config(args.config)
    people = load_people(args.config, trips)
    capacity = args.capacity or cfg.get("capacity", 4)

    result = solve(trips, people, capacity)
    print(f"Capacidad por coche: {capacity}")
    print(weekly_table(result.plan))
    print(fairness_summary(result.plan))
    if result.warnings:
        print("\nAvisos:")
        for w in result.warnings:
            print("  ⚠ ", w)
    if args.csv:
        Path(args.csv).write_text(roles_csv(result.plan), encoding="utf-8")
        print(f"\nRoles guardados en {args.csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
