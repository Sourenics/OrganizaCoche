"""Genera docs/index.html (GitHub Pages) a partir de web/index.template.html.

Por defecto incrusta data/horaris.sample.csv (nombres INVENTADOS). La página
publicada es pública, así que los datos reales nunca se incrustan: el
administrador los importa en la app como JSON y se quedan en su navegador.

Uso: python scripts/build_web.py              # datos de ejemplo (lo normal)
     python scripts/build_web.py --data data/horaris.csv   # sólo para uso local, no publicar
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAYS = ["dilluns", "dimarts", "dimecres", "dijous", "divendres"]


def seed(csv_path: Path, sample: bool) -> dict:
    cfg = json.loads((ROOT / "data/config.json").read_text(encoding="utf-8"))
    people: dict[str, dict] = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            p = people.setdefault(r["persona"], {"name": r["persona"], "active": True, "days": {}})
            # Marca por día: auto · drive (conduce) · pax (paquete) · solo (no comparte)
            mark = {"conduce": "drive", "paquete": "pax", "no_comparte": "solo"}.get((r.get("marca") or "").strip().lower(), "auto")
            if mark == "auto" and "no_comparte" in (r.get("rol_entrada_v6"), r.get("rol_salida_v6")):
                mark = "solo"
            p["days"][r["dia"]] = {
                "in": r["entrada"], "out": r["salida"],
                "flex": r.get("salida_flex") or "", "mark": mark,
            }
    for name, c in cfg.get("people", {}).items():
        if name in people and c.get("active") is False:
            people[name]["active"] = False
    return {"capacity": cfg.get("capacity", 4), "sample": sample, "people": list(people.values())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None, help="CSV de horarios (por defecto el de ejemplo)")
    args = ap.parse_args()
    csv_path = Path(args.data) if args.data else ROOT / "data/horaris.sample.csv"
    tpl = (ROOT / "web/index.template.html").read_text(encoding="utf-8")
    html = tpl.replace("__SEED__", json.dumps(seed(csv_path, sample=args.data is None), ensure_ascii=False))
    if args.data:
        print("AVISO: has incrustado datos reales. No publiques este docs/index.html.")
    out = ROOT / "docs/index.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"-> {out.relative_to(ROOT)} ({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
