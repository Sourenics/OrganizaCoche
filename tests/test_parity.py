"""Paridad Python ↔ JavaScript: el solver de la web (web/index.template.html) debe dar
exactamente el mismo reparto que src/cotxa/solver.py. Se ejecuta el JS con Node sobre
los mismos datos y se comparan roles, coches (con "también podrían") y avisos.

Si no hay Node instalado, el test se salta (no falla): el resto de la suite no lo necesita.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from cotxa.models import Person, Role, Trip
from cotxa.solver import solve

ROOT = Path(__file__).resolve().parents[1]
DAYS = ["dilluns", "dimarts", "dimecres", "dijous", "divendres"]
MARK_TO_ROLE = {"drive": Role.DRIVER, "pax": Role.PASSENGER, "solo": Role.SOLO}

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="hace falta Node.js para ejecutar el solver de la web")


def _seed() -> dict:
    spec = importlib.util.spec_from_file_location("build_web", ROOT / "scripts" / "build_web.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.seed(ROOT / "data" / "horaris.sample.csv", sample=True)


def _run_js(state: dict, bias: dict | None, tmp_path: Path) -> dict:
    """Ejecuta solve(state, bias) de la web en Node, con un DOM mínimo simulado."""
    tpl = (ROOT / "web" / "index.template.html").read_text(encoding="utf-8")
    js = tpl[tpl.rfind("<script>") + 8 : tpl.rfind("</script>")]
    js = js.replace("__SEED__", json.dumps(state, ensure_ascii=False))
    stub = """
const localStorage={getItem(){return null},setItem(){}};
const el=()=>({addEventListener(){},onclick:null,checked:false,value:"",classList:{toggle(){}}});
const document={body:{classList:{toggle(){}}},querySelector:el,querySelectorAll:()=>[],createElement:el};
const window={};
"""
    tail = f"""
const r=solve({json.dumps(state, ensure_ascii=False)}, {json.dumps(bias or {})});
process.stdout.write(JSON.stringify({{
  roles:r.roles,
  cars:r.cars.map(c=>[c.day,c.dir,c.time,c.driver,c.passengers,c.alternatives]),
  warnings:r.warnings,
}}));
"""
    script = tmp_path / "solver.js"
    script.write_text(stub + js + tail, encoding="utf-8")
    out = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout)


def _to_python(state: dict) -> tuple[list[Trip], dict[str, Person]]:
    """Misma conversión que hace la web: sólo personas activas y días con alguna hora."""
    trips, people = [], {}
    for p in state["people"]:
        if not p.get("active", True):
            continue
        cap = p.get("maxDrive") if state.get("useCaps") else None
        people[p["name"]] = Person(p["name"], max_drive=cap if isinstance(cap, int) else None)
        for d in DAYS:
            x = p["days"].get(d)
            if not x or not any(x.get(k) for k in ("in", "out", "inflex", "flex")):
                continue
            trips.append(Trip(
                p["name"], d, x.get("in", ""), x.get("out", ""),
                departure_flex=x.get("flex") or None,
                fixed_role=MARK_TO_ROLE.get(x.get("mark", "auto")),
                arrival_flex=x.get("inflex") or None,
            ))
    return trips, people


def _python_result(state: dict, bias: dict | None) -> dict:
    trips, people = _to_python(state)
    res = solve(trips, people, state.get("capacity", 4), bias=bias)
    return {
        "roles": {f"{p}|{d}": ("solo" if r is Role.SOLO else r.value) for (p, d), r in res.plan.roles.items()},
        "cars": [[c.slot.day, c.slot.direction, c.slot.time, c.driver, c.passengers, c.alternatives] for c in res.plan.cars],
        "warnings": res.warnings,
    }


def _norm(r: dict) -> dict:
    key = lambda c: json.dumps(c, ensure_ascii=False)
    return {"roles": r["roles"], "cars": sorted(r["cars"], key=key), "warnings": sorted(r["warnings"])}


def _check(state: dict, bias: dict | None, tmp_path: Path) -> None:
    py, js = _norm(_python_result(state, bias)), _norm(_run_js(state, bias, tmp_path))
    assert py["roles"] == js["roles"], "los roles (quién conduce cada día) difieren entre Python y la web"
    assert py["cars"] == js["cars"], "los coches o los 'también podrían' difieren entre Python y la web"
    assert py["warnings"] == js["warnings"], "los avisos difieren entre Python y la web"


def test_parity_sample_data(tmp_path):
    _check(_seed(), None, tmp_path)


def test_parity_with_all_features(tmp_path):
    """Marcas manuales, topes, compensación, horas flexibles, horas imposibles e inactivos a la vez."""
    st = _seed()
    st["useCaps"] = True
    for p in st["people"]:
        n = p["name"]
        if n == "Aina":
            p["days"]["dilluns"]["mark"] = "drive"
        if n == "Pau":
            p["days"]["dilluns"]["mark"] = "pax"
        if n == "Joan":
            p["maxDrive"] = 1
        if n == "Iris":
            p["maxDrive"] = 0
        if n == "Hug":
            p["days"]["dilluns"]["inflex"] = "8:00"
        if n == "Biel":
            p["days"]["divendres"]["inflex"] = "8:00"
        if n == "Empar":
            p["days"]["dimarts"]["out"] = "8:00"  # imposible: fuera con aviso
        if n == "Lluc":
            p["active"] = False
    bias = {"Carme": 0.5, "Neus": -0.3, "Biel": 1.0}
    _check(st, bias, tmp_path)
